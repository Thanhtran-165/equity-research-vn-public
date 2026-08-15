#!/usr/bin/env python3
"""Regression cho adapter schema BCTC vnstock_data 3.0 và 3.2.7."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statement_adapter import (  # noqa: E402
    StatementSchemaError,
    annual_rows,
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

    def test_missing_period_fails_closed(self):
        with self.assertRaises(StatementSchemaError):
            normalize_statement(pd.DataFrame({"value": [1, 2]}), "income")


if __name__ == "__main__":
    unittest.main()
