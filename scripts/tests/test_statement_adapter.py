#!/usr/bin/env python3
"""Regression cho adapter schema BCTC vnstock_data 3.0, 3.2.7 và 3.2.8."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statement_adapter import (  # noqa: E402
    StatementSchemaError,
    annual_rows,
    completed_annual_rows,
    combine_statements,
    normalize_statement,
)


class StatementAdapterTests(unittest.TestCase):
    def test_legacy_period_index_is_preserved(self):
        raw = pd.DataFrame(
            {"Net sales": [100.0, 110.0], "report_period": ["year", "year"]},
            index=["2024", "2025"],
        )
        got = normalize_statement(raw, "income")
        self.assertEqual(list(got.index), ["2024", "2025"])
        self.assertEqual(got.loc["2025", "Net sales"], 110.0)

    def test_unified_corporate_slugs_get_canonical_aliases(self):
        raw = pd.DataFrame({
            "period": [2024, 2025],
            "3_doanh_thu_thuan_ve_ban_hang_va_cung_cap_dich_vu": [10.0, 20.0],
            "loi_nhuan_sau_thue_cua_co_dong_cua_cong_ty_me": [1.0, 2.0],
            "19_lai_co_ban_tren_co_phieu_vn": [100.0, 200.0],
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(got.loc["2025", "Net sales"], 20.0)
        self.assertEqual(got.loc["2025", "Attributable to parent company"], 2.0)
        self.assertEqual(got.loc["2025", "EPS basic (VND)"], 200.0)

    def test_unified_bank_derives_total_operating_income(self):
        raw = pd.DataFrame({
            "period": [2025],
            "i_thu_nhap_lai_thuan": [100.0],
            "ii_lai_lo_thuan_tu_hoat_dong_dich_vu": [10.0],
            "iii_lai_lo_thuan_tu_hoat_dong_kinh_doanh_ngoai_hoi_va_vang": [-2.0],
            "xiii_loi_nhuan_sau_thue_xi_xii": [50.0],
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(got.loc["2025", "Total Operating Income"], 108.0)
        self.assertEqual(got.loc["2025", "Net profit/(loss) after tax"], 50.0)

    def test_wide_item_schema_is_transposed(self):
        raw = pd.DataFrame({
            "schema_group": ["income", "income"],
            "item": ["Net sales", "EPS basic (VND)"],
            "2024": [100.0, 10.0],
            "2025": [120.0, 12.0],
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(got.loc["2025", "Net sales"], 120.0)
        self.assertEqual(got.loc["2025", "EPS basic (VND)"], 12.0)

    def test_quarter_and_year_are_combined_for_period_oracle(self):
        quarter = pd.DataFrame({"period": ["2025-Q3", "2025-Q4"], "total_assets": [1, 2]})
        annual = pd.DataFrame({"period": [2024, 2025], "total_assets": [3, 4]})
        got = combine_statements(quarter, annual, "balance")
        self.assertEqual(len(got), 4)
        self.assertEqual(list(annual_rows(got).index), ["2024", "2025"])

    def test_alias_coalesces_new_and_old_schema_columns(self):
        raw = pd.DataFrame({
            "period": [2024, 2025],
            "d_von_chu_so_huu": [None, None],
            "b_von_chu_so_huu": [30.0, 40.0],
            "total_assets": [100.0, 120.0],
        })
        got = normalize_statement(raw, "balance")
        self.assertEqual(got.loc["2025", "Owner's Equity"], 40.0)

    def test_securities_schema_uses_net_revenue_not_deduction(self):
        income = pd.DataFrame({
            "period": [2025],
            "deduction_from_revenue": [None],
            "net_revenue": [987.0],
            "xi_loi_nhuan_ke_toan_sau_thue_tndn": [123.0],
            "11_1_loi_nhuan_sau_thue_phan_bo_cho_chu_so_huu": [120.0],
            "13_1_lai_co_ban_tren_co_phieu_dong_1_co_phieu_vn": [1500.0],
        })
        got = normalize_statement(income, "income")
        self.assertEqual(got.loc["2025", "Net sales"], 987.0)
        self.assertEqual(got.loc["2025", "Net profit/(loss) after tax"], 123.0)
        self.assertEqual(got.loc["2025", "Attributable to parent company"], 120.0)
        self.assertEqual(got.loc["2025", "EPS basic (VND)"], 1500.0)

        cash_flow = pd.DataFrame({
            "period": [2025],
            "luu_chuyen_tien_thuan_tu_hoat_dong_kinh_doanh_chung_khoan": [55.0],
        })
        got_cf = normalize_statement(cash_flow, "cash_flow")
        self.assertEqual(
            got_cf.loc["2025", "Net cash inflows/(outflows) from operating activities"],
            55.0,
        )

    def test_insurance_schema_gets_canonical_aliases(self):
        income = pd.DataFrame({
            "period": [2025],
            "5_doanh_thu_thuan_hdkd_bh_10_03_04": [456.0],
            "29_loi_nhuan_sau_thue_thu_nhap_doanh_nghiep": [44.0],
            "31_loi_nhuan_sau_thue_cua_co_dong_cua_cong_ty_me": [40.0],
            "32_lai_co_ban_tren_co_phieu_vn": [800.0],
        })
        got = normalize_statement(income, "income")
        self.assertEqual(got.loc["2025", "Net sales"], 456.0)
        self.assertEqual(got.loc["2025", "Net profit/(loss) after tax"], 44.0)
        self.assertEqual(got.loc["2025", "Attributable to parent company"], 40.0)
        self.assertEqual(got.loc["2025", "EPS basic (VND)"], 800.0)

        balance = pd.DataFrame({
            "period": [2025],
            "a_no_phai_tra_300_210_330": [600.0],
            "b_von_chu_so_huu_400_410_430": [400.0],
        })
        got_bs = normalize_statement(balance, "balance")
        self.assertEqual(got_bs.loc["2025", "Total Liabilities"], 600.0)
        self.assertEqual(got_bs.loc["2025", "Owner's Equity"], 400.0)

    def test_current_year_ltm_is_not_a_completed_annual_period(self):
        raw = pd.DataFrame({
            "period": [2024, 2025, 2026],
            "report_period": ["year", "year", "year"],
            "Net sales": [100.0, 110.0, 999.0],
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(list(annual_rows(got).index), ["2024", "2025", "2026"])
        self.assertEqual(
            list(completed_annual_rows(got, current_year=2026).index),
            ["2024", "2025"],
        )

    def test_missing_period_fails_closed(self):
        with self.assertRaises(StatementSchemaError):
            normalize_statement(pd.DataFrame({"value": [1, 2]}), "income")

    def test_vnstock_328_long_schema_uses_standardized_ids(self):
        raw = pd.DataFrame({
            "period": ["2025", "2025", "2024", "2024"],
            "id": ["IS_NET_REVENUE", "IS_NET_PROFIT_AFTER_TAX", "IS_NET_REVENUE", "IS_NET_PROFIT_AFTER_TAX"],
            "name": ["Net Revenue", "Net Profit", "Net Revenue", "Net Profit"],
            "order": [1, 2, 1, 2],
            "level": [1, 1, 1, 1],
            "unit": ["VNĐ"] * 4,
            "value": [200.0, 30.0, 180.0, 25.0],
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(list(got.index), ["2024", "2025"])
        self.assertEqual(got.loc["2025", "Net sales"], 200.0)
        self.assertEqual(got.loc["2025", "Net profit/(loss) after tax"], 30.0)

    def test_vnstock_328_standardized_fields_cover_four_statement_groups(self):
        income = pd.DataFrame({
            "period": ["2025"],
            "id": ["IS_TOTAL_NET_REVENUE_FROM_INSURANCE_BUSINESS"],
            "value": [456.0],
        })
        balance = pd.DataFrame({
            "period": ["2025"],
            "id": ["BS_TOTAL_ASSETS"],
            "value": [1000.0],
        })
        cash = pd.DataFrame({
            "period": ["2025"],
            "id": ["CF_NET_CASH_FLOWS_FROM_OPERATING_ACTIVITIES"],
            "value": [55.0],
        })
        self.assertEqual(normalize_statement(income, "income").loc["2025", "Net sales"], 456.0)
        self.assertEqual(normalize_statement(balance, "balance").loc["2025", "Total Assets"], 1000.0)
        self.assertEqual(
            normalize_statement(cash, "cash_flow").loc[
                "2025", "Net cash inflows/(outflows) from operating activities"
            ],
            55.0,
        )

    def test_vnstock_328_long_duplicate_period_id_fails_closed(self):
        raw = pd.DataFrame({
            "period": ["2025", "2025"],
            "id": ["IS_NET_REVENUE", "IS_NET_REVENUE"],
            "value": [1.0, 2.0],
        })
        with self.assertRaisesRegex(StatementSchemaError, "trùng"):
            normalize_statement(raw, "income")

    def test_zero_is_preserved_in_vnstock_328_long_schema(self):
        raw = pd.DataFrame({
            "period": ["2025"], "id": ["IS_NET_REVENUE"], "value": [0.0]
        })
        got = normalize_statement(raw, "income")
        self.assertEqual(got.loc["2025", "Net sales"], 0.0)

    def test_nan_is_preserved_as_missing_in_vnstock_328_long_schema(self):
        raw = pd.DataFrame({
            "period": ["2025"], "id": ["IS_NET_REVENUE"], "value": [float("nan")]
        })
        got = normalize_statement(raw, "income")
        self.assertTrue(pd.isna(got.loc["2025", "Net sales"]))


if __name__ == "__main__":
    unittest.main()
