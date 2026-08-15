#!/usr/bin/env python3
"""Test tính tổng quát của Fundamental Depth (earnings quality + CCC + DuPont 5/SGR).

Chạy 3 bộ data mẫu thuộc 3 ngành KHÁC NHAU — đảm bảo logic không crash, ra kết quả
hợp lý, và áp đúng đặc thù ngành:
- Ngân hàng: không có tồn kho → CCC phải = null (KHÔNG bịa)
- Nhà thầu: data thiếu chi tiết → CCC = null; cash conversion thấp do vốn lưu động
- Thép chu kỳ: cash conversion tốt, SGR tính được khi có payout

Chạy: python3 scripts/tests/test_fundamental_depth.py
"""
import sys

def cash_conversion(cfo, npat):
    """CFO/LNST từng năm — bỏ qua năm LNST ≤ 0 (âm/0 không có nghĩa)."""
    out = []
    for c, n in zip(cfo, npat):
        if n and n > 0:
            out.append(round(c / n, 2))
        else:
            out.append(None)
    return out

def ccc(revenue, cogs, receivables, inventory, payables):
    """CCC = DSO + DIO − DPO (ngày). Trả None nếu thiếu bất kỳ thành phần nào."""
    missing = [x is None for x in (revenue, cogs, receivables, inventory, payables)]
    if any(missing) or not revenue or not cogs or cogs <= 0:
        return None
    dso = receivables / revenue * 365 if revenue else None
    dio = inventory / cogs * 365 if inventory is not None else None
    dpo = payables / cogs * 365 if payables is not None else None
    if dio is None or dpo is None:
        return None
    return {"dso": round(dso, 1), "dio": round(dio, 1), "dpo": round(dpo, 1),
            "ccc_days": round(dso + dio - dpo, 1)}

def dupont5(npat, pretax, ebit, revenue, total_assets, equity):
    """DuPont 5 bước — None nếu thiếu dữ liệu."""
    if None in (npat, pretax, ebit, revenue, total_assets, equity) or pretax == 0 or ebit == 0:
        return None
    return {"tax_burden": round(npat / pretax, 3), "interest_burden": round(pretax / ebit, 3),
            "op_margin": round(ebit / revenue, 4), "asset_turn": round(revenue / total_assets, 3),
            "leverage": round(total_assets / equity, 3)}

def sgr(roe, dividends, npat):
    """SGR = ROE × (1 − payout) — None nếu thiếu cổ tức."""
    if roe is None or dividends is None or npat is None or npat == 0:
        return None
    payout = min(max(dividends / npat, 0), 1)
    return round(roe * (1 - payout), 4)


def avg_balance_roe(npat, equity_begin, equity_end):
    """ROE với vốn bình quân (W2-2): year0 dùng equity_end (thiếu begin)."""
    out = []
    for i, n in enumerate(npat):
        eq = (equity_begin[i] + equity_end[i]) / 2 if equity_begin[i] is not None else equity_end[i]
        out.append(round(n / eq * 100, 2) if eq else None)
    return out

def accrual_ratio(npat, cfo, total_assets_avg):
    """(LNST − CFO) / Tổng TS bình quân — None nếu thiếu data."""
    out = []
    for i in range(len(npat)):
        if total_assets_avg[i] is None:
            out.append(None)
            continue
        out.append(round((npat[i] - cfo[i]) / total_assets_avg[i], 4))
    return out

def run():
    fails = []

    # ── Case 1: NGÂN HÀNG — không tồn kho → CCC phải null ──
    bank_cfo = [5000, 5200, 5400, 5600, 5800]
    bank_npat = [4800, 5000, 5200, 5400, 5600]
    cc = cash_conversion(bank_cfo, bank_npat)
    if cc[-1] < 0.8:
        fails.append(f"ngân hàng: cash conversion {cc[-1]} < 0.8 (kỳ vọng ~1.0)")
    c = ccc(40000, None, None, None, None)  # ngân hàng không có COGS/tồn kho
    if c is not None:
        fails.append(f"ngân hàng: CCC phải null nhưng = {c}")
    d5 = dupont5(5600, 7000, 8000, 40000, 90000, 7000)
    if d5 is None:
        fails.append("ngân hàng: DuPont 5 phải tính được (đủ data)")
    elif abs(d5["tax_burden"] - 0.8) > 0.01 or abs(d5["interest_burden"] - 0.875) > 0.01:
        fails.append(f"ngân hàng: DuPont 5 sai {d5}")

    # ── Case 2: NHÀ THẦU — thiếu data chi tiết → CCC null; cash conversion thấp ──
    ctd_cfo = [421, -1627, 1467, -857, -831]
    ctd_npat = [24, 21, 188, 371, 781]
    cc2 = cash_conversion(ctd_cfo, ctd_npat)
    if cc2[-1] is None or cc2[-1] > 0.5:
        fails.append(f"nhà thầu: cash conversion năm cuối phải thấp/âm (vốn lưu động) — {cc2[-1]}")
    c2 = ccc(30699, 27624, None, None, None)  # thiếu receivables/inventory/payables
    if c2 is not None:
        fails.append(f"nhà thầu thiếu data: CCC phải null nhưng = {c2}")
    d5b = dupont5(781, None, None, 30699, 34442, 9385)
    if d5b is not None:
        fails.append(f"nhà thầu thiếu EBIT/LNTT: DuPont 5 phải null nhưng = {d5b}")

    # ── Case 3: THÉP CHU KỲ — đủ data → đầy đủ; SGR theo payout ──
    st_cfo = [42000, 18000, 25000, 28000, 35000]
    st_npat = [34521, 8444, 6835, 12021, 15515]
    cc3 = cash_conversion(st_cfo, st_npat)
    if cc3[-1] < 0.8:
        fails.append(f"thép: cash conversion {cc3[-1]} < 0.8 (kỳ vọng tốt)")
    c3 = ccc(158332, 120000, 28000, 30000, 22000)
    if c3 is None:
        fails.append("thép: CCC phải tính được (đủ data)")
    elif not (0 < c3["ccc_days"] < 200):
        fails.append(f"thép: CCC {c3} ngoài khoảng hợp lý")
    d5c = dupont5(15515, 20000, 24000, 158332, 240000, 145000)
    if d5c is None:
        fails.append("thép: DuPont 5 phải tính được")
    sg = sgr(0.107, 3000, 15515)
    if sg is None:
        fails.append("thép: SGR phải tính được")
    elif not (0.06 < sg < 0.12):
        fails.append(f"thép: SGR {sg} ngoài khoảng hợp lý (0.06-0.12)")
    sg_nodata = sgr(0.107, None, 15515)
    if sg_nodata is not None:
        fails.append("thiếu cổ tức: SGR phải null nhưng tính ra")

    # W2-2: average balances — ROE bình quân khác ROE cuối kỳ khi vốn biến động
    eq_b = [100, 110, 120, 130, 140]
    eq_e = [110, 120, 130, 140, 150]
    roe_avg = avg_balance_roe([11, 12, 13, 14, 15], eq_b, eq_e)
    # year0: (100+110)/2=105 → 11/105 = 10.48%; year1: (110+120)/2=115 → 12/115 = 10.43%
    # (khác ROE cuối kỳ: 11/110=10.0%, 12/120=10.0% — bình quân nhạy hơn với vốn biến động)
    if abs(roe_avg[0] - 10.48) > 0.01 or abs(roe_avg[1] - 10.43) > 0.01:
        fails.append(f"average-balance ROE sai: {roe_avg}")
    if roe_avg[0] == 10.0:
        fails.append("ROE vẫn dùng số dư cuối kỳ (không phải bình quân)")
    # W2-2: accrual — nhà thầu (LNST > CFO → accrual dương), thép (CFO > LNST → âm)
    acc_bank = accrual_ratio([5600], [5800], [90000])
    if acc_bank[0] is None or abs(acc_bank[0] - (-0.0022)) > 0.001:
        fails.append(f"accrual ngân hàng sai: {acc_bank}")
    acc_ctd = accrual_ratio([781], [-831], [34442])
    if acc_ctd[0] is None or acc_ctd[0] < 0.03:
        fails.append(f"accrual nhà thầu phải dương (LNST > CFO): {acc_ctd}")
    acc_nodata = accrual_ratio([781], [-831], [None])
    if acc_nodata[0] is not None:
        fails.append("accrual thiếu data phải null")

    if fails:
        print("❌ FAIL:", *fails, sep="\n  - ")
        sys.exit(1)
    print("✅ FUNDAMENTAL DEPTH OK — 3 ngành (ngân hàng/nhà thầu/thép):")
    print("   - cash conversion: ngân hàng ~1.0 ✓, nhà thầu thấp/âm ✓, thép ≥0.8 ✓")
    print("   - CCC: ngân hàng null ✓, nhà thầu thiếu-data null ✓, thép tính đúng ✓")
    print("   - DuPont 5 + SGR: đủ data tính, thiếu data null (không bịa) ✓")
    print("   - W2-2: average-balance ROE ✓, accrual ratio (ngân hàng âm, nhà thầu dương) ✓")

if __name__ == "__main__":
    run()
