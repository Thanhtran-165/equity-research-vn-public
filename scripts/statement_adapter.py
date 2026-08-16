#!/usr/bin/env python3
"""Chuẩn hóa BCTC vnstock_data cũ/mới về contract nội bộ ổn định.

vnstock_data 3.0 trả bảng theo kỳ ở index và tên chỉ tiêu tiếng Anh, trong khi
3.2.7 trả bảng theo hàng với cột ``period`` và tên chỉ tiêu dạng slug. Adapter
này giữ nguyên dữ liệu nguồn, chỉ bổ sung các alias canonical mà builder và
verifier đã kiểm định sử dụng.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

import pandas as pd


class StatementSchemaError(ValueError):
    """Schema BCTC không đủ rõ để chuẩn hóa an toàn."""


def _period_text(value) -> str:
    text = str(value).strip()
    if re.fullmatch(r"20\d{2}\.0", text):
        text = text[:-2]
    return text


def _looks_like_period(value) -> bool:
    return bool(re.fullmatch(r"20\d{2}(?:[-/]?Q[1-4])?", _period_text(value), re.I))


def _wide_to_rows(frame: pd.DataFrame) -> pd.DataFrame | None:
    """Chuyển schema item×năm của Finance 3.2.7 sang period×field."""
    period_cols = [c for c in frame.columns if _looks_like_period(c)]
    if not period_cols:
        return None
    item_col = next((c for c in ("item", "name", "metric") if c in frame.columns), None)
    if item_col is None:
        return None
    slim = frame[[item_col, *period_cols]].copy()
    slim[item_col] = slim[item_col].astype(str)
    # Một vài payload có cùng item ở nhiều schema_group. Không cộng số liệu;
    # lấy giá trị không-null đầu tiên và giữ fail-closed nếu không có gì dùng được.
    slim = slim.drop_duplicates(subset=[item_col], keep="first").set_index(item_col)
    out = slim.T
    out.index = [_period_text(v) for v in out.index]
    out.index.name = "period"
    return out


def normalize_statement(frame: pd.DataFrame, statement: str) -> pd.DataFrame:
    """Chuẩn hóa một payload income/balance/cash-flow thành period×field."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        raise StatementSchemaError(f"{statement}: payload rỗng hoặc không phải DataFrame")

    if "period" in frame.columns:
        out = frame.copy()
        out["period"] = out["period"].map(_period_text)
        out = out.set_index("period", drop=True)
    elif all(_looks_like_period(v) for v in frame.index):
        out = frame.copy()
        out.index = [_period_text(v) for v in out.index]
        out.index.name = "period"
    else:
        out = _wide_to_rows(frame)
        if out is None:
            raise StatementSchemaError(
                f"{statement}: không tìm thấy period ở cột, index hoặc schema item×kỳ"
            )

    if out.index.has_duplicates:
        duplicates = sorted(set(out.index[out.index.duplicated()].tolist()))
        raise StatementSchemaError(f"{statement}: period trùng lặp {duplicates[:5]}")
    if not all(_looks_like_period(v) for v in out.index):
        bad = [str(v) for v in out.index if not _looks_like_period(v)]
        raise StatementSchemaError(f"{statement}: period không hợp lệ {bad[:5]}")

    out["report_period"] = ["year" if re.fullmatch(r"20\d{2}", p) else "quarter" for p in out.index]
    out = _add_canonical_fields(out, statement)
    return out.sort_index()


def combine_statements(quarter: pd.DataFrame, annual: pd.DataFrame, statement: str) -> pd.DataFrame:
    """Gộp kỳ quý và năm, không cho phép một period tự mâu thuẫn."""
    q = normalize_statement(quarter, statement)
    y = normalize_statement(annual, statement)
    overlap = set(q.index) & set(y.index)
    if overlap:
        raise StatementSchemaError(f"{statement}: period quý/năm trùng nhau {sorted(overlap)[:5]}")
    return pd.concat([q, y], axis=0, sort=False).sort_index()


def annual_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Lấy các năm tài chính từ contract đã chuẩn hóa."""
    if "report_period" not in frame.columns:
        raise StatementSchemaError("thiếu report_period sau normalize")
    return frame[frame["report_period"].eq("year")].sort_index()


def completed_annual_rows(frame: pd.DataFrame, current_year: int | None = None) -> pd.DataFrame:
    """Chỉ lấy năm tài chính đã kết thúc trước năm đang chạy.

    Một số payload VCI gắn dòng LTM/quý hiện tại thành một dòng ``year`` (ví dụ
    CTD có nhãn 2026 vào tháng 8/2026). Dòng đó không phải BCTC năm hoàn chỉnh và
    không được phép trở thành năm định giá. Giữ toàn bộ dòng trong source-pack;
    chỉ loại khỏi chuỗi annual dùng để dựng báo cáo.
    """
    rows = annual_rows(frame)
    cutoff = int(current_year or date.today().year) - 1
    mask = [int(str(period)[:4]) <= cutoff for period in rows.index]
    return rows.loc[mask]


def _alias(frame: pd.DataFrame, target: str, names: Iterable[str]) -> None:
    # Payload 3.2.7 có thể đồng thời chứa schema cũ/mới: một cột tồn tại nhưng
    # toàn NaN ở các năm mới, cột kế tiếp mới có số. Coalesce theo thứ tự ưu tiên,
    # tuyệt đối không dừng chỉ vì nhìn thấy tên cột đầu tiên.
    merged = pd.to_numeric(frame[target], errors="coerce") if target in frame.columns else None
    for name in names:
        if name not in frame.columns or name == target:
            continue
        candidate = pd.to_numeric(frame[name], errors="coerce")
        merged = candidate if merged is None else merged.combine_first(candidate)
    if merged is not None:
        frame[target] = merged


def _add_canonical_fields(frame: pd.DataFrame, statement: str) -> pd.DataFrame:
    out = frame.copy()
    if statement == "income":
        _alias(out, "Net sales", (
            "3_doanh_thu_thuan_ve_ban_hang_va_cung_cap_dich_vu",
            # Chứng khoán: dùng doanh thu thuần, tuyệt đối không bắt substring
            # ``deduction_from_revenue`` (khoản giảm trừ, thường là NaN).
            "net_revenue",
            # Bảo hiểm TT51.
            "5_doanh_thu_thuan_hdkd_bh_10_03_04",
            "5_1_doanh_thuan_bh_va_ccdv",
            "Net revenue", "Revenue", "Doanh thu thuần",
        ))
        _alias(out, "Attributable to parent company", (
            "11_1_loi_nhuan_sau_thue_phan_bo_cho_chu_so_huu",
            "31_loi_nhuan_sau_thue_cua_co_dong_cua_cong_ty_me",
            "loi_nhuan_sau_thue_cua_co_dong_cua_cong_ty_me",
            "xv_loi_nhuan_sau_thue_cua_co_dong_cua_ngan_hang_me_xiii_xiv",
            "Net profit attributable to shareholders",
        ))
        _alias(out, "Net profit/(loss) after tax", (
            "xi_loi_nhuan_ke_toan_sau_thue_tndn",
            "29_loi_nhuan_sau_thue_thu_nhap_doanh_nghiep",
            "xiii_loi_nhuan_sau_thue_xi_xii",
            "18_loi_nhuan_sau_thue_thu_nhap_doanh_nghiep",
            "Attributable to parent company", "Profit after tax",
        ))
        _alias(out, "EPS basic (VND)", (
            "13_1_lai_co_ban_tren_co_phieu_dong_1_co_phieu_vn",
            "32_lai_co_ban_tren_co_phieu_vn",
            "19_lai_co_ban_tren_co_phieu_vn", "lai_co_ban_tren_co_phieu_bctc_vnd",
            "EPS basic", "Earnings per share",
        ))
        _alias(out, "Gross Profit", (
            "5_loi_nhuan_gop_ve_ban_hang_va_cung_cap_dich_vu", "Lợi nhuận gộp",
        ))
        if "Total Operating Income" not in out.columns:
            bank_components = (
                "i_thu_nhap_lai_thuan",
                "ii_lai_lo_thuan_tu_hoat_dong_dich_vu",
                "iii_lai_lo_thuan_tu_hoat_dong_kinh_doanh_ngoai_hoi_va_vang",
                "iv_lai_lo_thuan_tu_mua_ban_chung_khoan_kinh_doanh",
                "v_lai_lo_thuan_tu_mua_ban_chung_khoan_dau_tu",
                "vi_lai_lo_thuan_tu_hoat_dong_khac",
                "vii_thu_nhap_tu_gop_von_mua_co_phan",
            )
            present = [pd.to_numeric(out[c], errors="coerce") for c in bank_components if c in out.columns]
            if present:
                out["Total Operating Income"] = pd.concat(present, axis=1).sum(axis=1, min_count=1)
    elif statement == "balance":
        _alias(out, "Total Assets", ("total_assets", "a_tai_san"))
        _alias(out, "Total Liabilities", (
            "a_no_phai_tra_300_210_330", "a_no_phai_tra_300_310_340",
            "liabilities", "c_no_phai_tra", "a_no_phai_tra",
        ))
        _alias(out, "Owner's Equity", (
            "b_von_chu_so_huu_400_410_430", "b_von_chu_so_huu_400_410_420",
            "d_von_chu_so_huu", "b_von_chu_so_huu", "viii_von_va_cac_quy",
        ))
        if "Owner's Equity" not in out.columns and {"Total Assets", "Total Liabilities"}.issubset(out.columns):
            out["Owner's Equity"] = out["Total Assets"] - out["Total Liabilities"]
        _alias(out, "Inventory", ("iv_hang_ton_kho", "1_hang_ton_kho", "Inventories", "Hàng tồn kho"))
        _alias(out, "Paid-in capital", ("1_von_gop_cua_chu_so_huu", "a_von_dieu_le", "Charter capital", "Vốn điều lệ"))
    elif statement == "cash_flow":
        _alias(out, "Net cash inflows/(outflows) from operating activities", (
            "luu_chuyen_tien_thuan_tu_hoat_dong_kinh_doanh_chung_khoan",
            "luu_chuyen_tien_thuan_tu_hdkd",
            "luu_chuyen_tien_thuan_tu_hoat_dong_kinh_doanh",
            "net_cash_flows_from_operating_activities", "Net cash from operating activities",
        ))
        _alias(out, "Purchases of fixed assets and other long term assets", (
            "payment_for_fixed_assets_constructions_and_other_long_term_assets",
            "purchase_of_fixed_assets", "Mua sắm tài sản",
        ))
    else:
        raise StatementSchemaError(f"loại báo cáo không hỗ trợ: {statement}")
    return out
