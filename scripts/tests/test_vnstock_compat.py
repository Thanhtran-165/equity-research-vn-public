#!/usr/bin/env python3
"""Test offline cho compatibility gate; không gọi vnstock/network."""

import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vnstock_compat import (  # noqa: E402
    CompatibilityGateError,
    REGISTRY_PATH,
    fingerprint_statement,
    probe_api_surface,
    run_schema_gate,
    statement_request_kwargs,
)


class FakeEquity:
    def income_statement(self, period, lang):
        return None

    def balance_sheet(self, period, lang):
        return None

    def cash_flow(self, period, lang):
        return None


class FakeEquityProxy:
    def __call__(self, symbol):
        return FakeEquity()


class FakeFundamental:
    @property
    def equity(self):
        return FakeEquityProxy()


class FakeQuote:
    def history(self, start, end):
        return None


def fake_module(version="3.2.2"):
    return types.SimpleNamespace(
        __version__=version,
        Fundamental=FakeFundamental,
        Quote=FakeQuote,
    )


def old_frames():
    income_q = pd.DataFrame(
        {"Net sales": [100], "Net profit/(loss) after tax": [10]}, index=["2025-Q1"]
    )
    income_y = pd.DataFrame(
        {"Net sales": [400], "Net profit/(loss) after tax": [40]}, index=["2024"]
    )
    balance_q = pd.DataFrame(
        {"Total Assets": [1000], "Owner's Equity": [300]}, index=["2025-Q1"]
    )
    balance_y = pd.DataFrame(
        {"Total Assets": [900], "Owner's Equity": [280]}, index=["2024"]
    )
    cash_q = pd.DataFrame(
        {"Net cash inflows/(outflows) from operating activities": [20]}, index=["2025-Q1"]
    )
    cash_y = pd.DataFrame(
        {"Net cash inflows/(outflows) from operating activities": [80]}, index=["2024"]
    )
    return {
        "income": (income_q, income_y),
        "balance": (balance_q, balance_y),
        "cash_flow": (cash_q, cash_y),
    }


def new_frames():
    income_q = pd.DataFrame(
        {"period": ["2025-Q1"], "3_doanh_thu_thuan_ve_ban_hang_va_cung_cap_dich_vu": [100],
         "xi_loi_nhuan_ke_toan_sau_thue_tndn": [10]}
    )
    income_y = pd.DataFrame(
        {"period": [2024], "3_doanh_thu_thuan_ve_ban_hang_va_cung_cap_dich_vu": [400],
         "xi_loi_nhuan_ke_toan_sau_thue_tndn": [40]}
    )
    balance_q = pd.DataFrame(
        {"period": ["2025-Q1"], "total_assets": [1000], "b_von_chu_so_huu_400_410_430": [300]}
    )
    balance_y = pd.DataFrame(
        {"period": [2024], "total_assets": [900], "b_von_chu_so_huu_400_410_430": [280]}
    )
    cash_q = pd.DataFrame(
        {"period": ["2025-Q1"], "net_cash_flows_from_operating_activities": [20]}
    )
    cash_y = pd.DataFrame(
        {"period": [2024], "net_cash_flows_from_operating_activities": [80]}
    )
    return {
        "income": (income_q, income_y),
        "balance": (balance_q, balance_y),
        "cash_flow": (cash_q, cash_y),
    }


def long_frames():
    def frame(period, rows):
        return pd.DataFrame({
            "period": [period] * len(rows),
            "id": [row[0] for row in rows],
            "value": [row[1] for row in rows],
        })
    return {
        "income": (
            frame("2025-Q1", [("IS_NET_REVENUE", 100), ("IS_NET_PROFIT_AFTER_TAX", 10)]),
            frame("2024", [("IS_NET_REVENUE", 400), ("IS_NET_PROFIT_AFTER_TAX", 40)]),
        ),
        "balance": (
            frame("2025-Q1", [("BS_TOTAL_ASSETS", 1000), ("BS_EQUITY", 300)]),
            frame("2024", [("BS_TOTAL_ASSETS", 900), ("BS_EQUITY", 280)]),
        ),
        "cash_flow": (
            frame("2025-Q1", [("CF_NET_CASH_FLOWS_FROM_OPERATING_ACTIVITIES", 20)]),
            frame("2024", [("CF_NET_CASH_FLOWS_FROM_OPERATING_ACTIVITIES", 80)]),
        ),
    }


class CompatibilityGateTests(unittest.TestCase):
    def test_official_version_pair_and_dynamic_instance_surface(self):
        with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
            result = probe_api_surface(fake_module())
        self.assertEqual(result["tested_version"], "3.2.8")
        self.assertFalse(result["api_surface_checked"])
        self.assertEqual(result["distribution_version"], "3.2.7")
        self.assertEqual(result["module_version"], "3.2.2")

    def test_unsupported_version_pair_fails_closed(self):
        with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
            with self.assertRaises(CompatibilityGateError):
                probe_api_surface(fake_module("3.2.3"), fundamental=FakeFundamental())

    def test_missing_statement_method_fails_closed(self):
        class MissingEquity:
            def income_statement(self, period, lang):
                return None

            def balance_sheet(self, period, lang):
                return None

        with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
            with self.assertRaises(CompatibilityGateError):
                probe_api_surface(
                    fake_module(), fundamental=FakeFundamental(), equity_api=MissingEquity()
                )

    def _runtime(self):
        with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
            return probe_api_surface(fake_module(), fundamental=FakeFundamental())

    def _runtime_328(self):
        with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.8"):
            return probe_api_surface(fake_module(), fundamental=FakeFundamental())

    def _registry_copy(self, directory):
        path = Path(directory) / "registry.json"
        shutil.copyfile(REGISTRY_PATH, path)
        return path

    def test_old_shape_writes_fingerprint(self):
        with tempfile.TemporaryDirectory() as work:
            with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
                result = run_schema_gate(old_frames(), work_dir=work, runtime=self._runtime())
            self.assertEqual(result["status"], "supported")
            self.assertEqual(result["frames"]["income"]["quarter"]["shape_mode"], "period_index_rows")
            self.assertEqual(result["frames"]["income"]["quarter"]["units_assumptions"]["status"], "not_verified")
            self.assertTrue((Path(work) / "schema-fingerprint.json").exists())

    def test_new_shape_writes_fingerprint(self):
        with tempfile.TemporaryDirectory() as work:
            with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
                result = run_schema_gate(new_frames(), work_dir=work, runtime=self._runtime())
            self.assertEqual(result["frames"]["income"]["quarter"]["shape_mode"], "period_column_rows")
            saved = json.loads((Path(work) / "schema-fingerprint.json").read_text())
            self.assertEqual(saved["tested_version"], "3.2.8")

    def test_long_shape_writes_fingerprint_for_328(self):
        with tempfile.TemporaryDirectory() as work:
            with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.8"):
                result = run_schema_gate(long_frames(), work_dir=work, runtime=self._runtime_328())
            self.assertEqual(result["status"], "supported")
            self.assertEqual(result["frames"]["income"]["quarter"]["shape_mode"], "long_period_id_rows")
            self.assertEqual(result["tested_distribution_version"], "3.2.8")

    def test_statement_request_is_version_aware_without_fallback(self):
        self.assertEqual(
            statement_request_kwargs({"distribution_version": "3.2.7"}, "year"),
            {"period": "year", "lang": "en"},
        )
        self.assertEqual(
            statement_request_kwargs({"distribution_version": "3.2.8"}, "year"),
            {"period": "year", "lang": "en", "format": "time_series"},
        )

    def test_missing_required_statement_key_fails_closed(self):
        frames = old_frames()
        del frames["balance"]
        with self.assertRaisesRegex(CompatibilityGateError, "thiếu=.*balance"):
            run_schema_gate(frames, work_dir=tempfile.mkdtemp(), runtime=self._runtime())

    def test_required_columns_all_nan_fail_closed(self):
        frames = old_frames()
        frames["income"] = (
            pd.DataFrame(
                {"Net sales": [float("nan")], "Net profit/(loss) after tax": [float("nan")]},
                index=["2025-Q1"],
            ),
            frames["income"][1],
        )
        with self.assertRaisesRegex(CompatibilityGateError, "không có dữ liệu khả dụng"):
            run_schema_gate(frames, work_dir=tempfile.mkdtemp(), runtime=self._runtime())

    def test_zero_is_a_valid_required_numeric_value(self):
        frames = old_frames()
        frames["income"] = (
            pd.DataFrame(
                {"Net sales": [0], "Net profit/(loss) after tax": [0]}, index=["2025-Q1"]
            ),
            frames["income"][1],
        )
        with tempfile.TemporaryDirectory() as work:
            result = run_schema_gate(frames, work_dir=work, runtime=self._runtime())
        self.assertEqual(result["status"], "supported")

    def test_reused_fingerprint_detects_tamper_and_stale_registry(self):
        from vnstock_compat import validate_reused_schema_fingerprint

        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as reg_dir:
            registry_path = self._registry_copy(reg_dir)
            with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
                run_schema_gate(
                    old_frames(),
                    work_dir=work,
                    runtime=self._runtime(),
                    registry_path=registry_path,
                )
                self.assertEqual(
                    validate_reused_schema_fingerprint(work, registry_path=registry_path)["status"],
                    "supported",
                )
            artifact = Path(work) / "schema-fingerprint.json"
            payload = json.loads(artifact.read_text())
            payload["frames"]["income"]["quarter"]["status"] = "tampered"
            artifact.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(CompatibilityGateError):
                validate_reused_schema_fingerprint(work, registry_path=registry_path)

            # Rebuild a valid artifact, then change registry bytes: stale
            # registry must block even when artifact checksum itself is valid.
            with patch("vnstock_compat.importlib.metadata.version", return_value="3.2.7"):
                run_schema_gate(
                    old_frames(),
                    work_dir=work,
                    runtime=self._runtime(),
                    registry_path=registry_path,
                )
            registry = json.loads(registry_path.read_text())
            registry["registry_version"] = 99
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(CompatibilityGateError):
                validate_reused_schema_fingerprint(work, registry_path=registry_path)

    def test_unknown_shape_blocks_without_mapping(self):
        with self.assertRaises(CompatibilityGateError):
            fingerprint_statement(pd.DataFrame({"as_of": ["2025"], "value": [1]}), "income")


if __name__ == "__main__":
    unittest.main()
