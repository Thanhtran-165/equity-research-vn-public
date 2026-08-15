#!/usr/bin/env python3
"""Focused regressions for Phase A wave 3 (REQ-022/REQ-059).

No network is used: vnstock_data is replaced with a deterministic Finance
fixture so zero values, year alignment, rounding and negative mutations are
tested independently of API availability.
"""
import csv
import importlib.util
import json
import os
import sys
import tempfile
import types

import pandas as pd
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VERIFIER = os.path.join(ROOT, "scripts", "independent_verifier.py")

spec = importlib.util.spec_from_file_location("independent_verifier", VERIFIER)
iv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iv)

registry = yaml.safe_load(open(os.path.join(ROOT, "requirements.yaml")))
REQ = {r["id"]: r for r in registry["requirements"]}


class FakeFinance:
    def __init__(self, source, symbol):
        self.symbol = symbol

    def income_statement(self):
        return pd.DataFrame(
            {
                "report_period": ["year", "year"],
                "Net sales": [0.0, 999e9],
                "Attributable to parent company": [15_611_975.0, 999e9],
                "EPS basic": [10.0, 999.0],
            },
            index=["2024", "2025"],
        )

    def balance_sheet(self):
        return pd.DataFrame(
            {
                "report_period": ["year", "year"],
                "Total Assets": [79.6e9, 120.3e9],
            },
            index=["2024", "2025"],
        )


fake_vnstock = types.ModuleType("vnstock_data")
fake_vnstock.Finance = FakeFinance
sys.modules["vnstock_data"] = fake_vnstock


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(value, f)


def test_req022_old_period_and_mutation():
    with tempfile.TemporaryDirectory(prefix="req022_wave3_") as work:
        write_json(
            os.path.join(work, "data/financials.json"),
            {
                "revenue_ty": {"2018": 30.01, "2019": 24.46},
                "npatmi_ty": {"2018": -189.68, "2019": -165.87},
                "eps_vnd": {"2018": -4360.0, "2019": -3813.0},
            },
        )
        html = """<script>const DATA = {
          \"years\":[2018,2019], \"revenue\":[30.01,24.46],
          \"netProfit\":[-189.68,-165.87], \"eps\":[-4360,-3813]
        };</script>"""
        iv.REPORT = os.path.join(work, "TEST_Complete_Report.html")
        ok, evidence = iv.verify_data_accuracy(REQ["REQ-022"], html)
        assert ok and evidence["checked"] == 6, evidence

        fin_path = os.path.join(work, "data/financials.json")
        fin = json.load(open(fin_path))
        fin["revenue_ty"]["2019"] = 999.0
        write_json(fin_path, fin)
        ok, evidence = iv.verify_data_accuracy(REQ["REQ-022"], html)
        assert not ok and any("revenue_ty[2019]" in x for x in evidence["mismatches"]), evidence


def test_req059_zero_same_year_rounding_and_mutation():
    with tempfile.TemporaryDirectory(prefix="req059_wave3_") as work:
        iv.TICKER = "TEST"
        iv.REPORT = os.path.join(work, "TEST_Complete_Report.html")
        open(iv.REPORT, "w").write("<html></html>")
        write_json(
            os.path.join(work, "data/financials.json"),
            {
                "revenue_ty": {"2024": 0.0},
                "npatmi_ty": {"2024": 0.02},
                "eps_vnd": {"2024": 10.0},
                "overview": {},
            },
        )
        write_json(os.path.join(work, "data/balance_sheet.json"), {"Total Assets": {"2024": 79.6e9}})
        write_json(os.path.join(work, "data/cash_flow.json"), {"Net cash from operating activities": {"2024": 1.0}})
        write_json(
            os.path.join(work, ".task-state/task-state.json"),
            {"phases": {"phase1_data": {"result": {"data_source": "fixture"}}}},
        )
        write_json(os.path.join(work, "data/peers.json"), {"source": "fixture", "peers": []})
        write_json(os.path.join(work, "verified-dashboard-data.json"), {"_provenance": {"source": "fixture"}})

        source = os.path.join(work, "source-pack")
        os.makedirs(source)
        with open(os.path.join(source, "income_statement_sponsor.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["period", "report_period", "Net sales", "Attributable to parent company", "EPS basic"])
            w.writerow(["2024", "year", 0.0, 15_611_975.0, 10.0])
        with open(os.path.join(source, "balance_sheet_sponsor.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["period", "report_period", "Total Assets"])
            w.writerow(["2024", "year", 79.6e9])

        ok, evidence = iv.verify_data_provenance(REQ["REQ-059"], "<html></html>")
        assert ok, evidence  # ignores API-only 2025, accepts 0 and 0.0156 -> 0.02 rounding

        fin_path = os.path.join(work, "data/financials.json")
        fin = json.load(open(fin_path))
        fin["revenue_ty"]["2024"] = 1.0
        write_json(fin_path, fin)
        ok, evidence = iv.verify_data_provenance(REQ["REQ-059"], "<html></html>")
        assert not ok and any("revenue_ty spot-check FAIL" in x for x in evidence["issues"]), evidence


def test_req062_financial_schema_inventory_na_and_zero_mutation():
    with tempfile.TemporaryDirectory(prefix="req062_wave3_") as work:
        iv.REPORT = os.path.join(work, "TEST_Complete_Report.html")
        open(iv.REPORT, "w").write("<html></html>")
        years = [2021, 2022, 2023, 2024, 2025]
        revenue = [1168.04, 1144.07, 1093.68, 1502.09, 2213.57]
        financials = {
            "years": [str(y) for y in years],
            "revenue": revenue[:], "netProfit": [1] * 5, "eps": [1] * 5,
            "totalAssets": [10] * 5, "equity": [5] * 5,
            "capex": [1] * 5, "cfo": [1] * 5, "inventory_fin": [None] * 5,
        }
        write_json(os.path.join(work, "verified-dashboard-data.json"), {
            "sector": "finance", "financials": financials,
        })
        source = os.path.join(work, "source-pack")
        os.makedirs(source)
        specs = {
            "income_statement_sponsor.csv": (
                ["period", "report_period", "Total Operating Income", "Attributable to parent company", "EPS basic"],
                lambda i: [years[i], "year", revenue[i] * 1e9, 1e9, 1],
            ),
            "balance_sheet_sponsor.csv": (
                ["period", "report_period", "Total Assets", "Owner's Equity"],
                lambda i: [years[i], "year", 10e9, 5e9],
            ),
            "cash_flow_sponsor.csv": (
                ["period", "report_period", "Purchases of fixed assets", "Net cash from operating activities"],
                lambda i: [years[i], "year", -1e9, 1e9],
            ),
        }
        for name, (header, row_fn) in specs.items():
            with open(os.path.join(source, name), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(header)
                for i in range(5):
                    w.writerow(row_fn(i))

        ok, evidence = iv.verify_period_integrity(REQ["REQ-062"], "<html></html>")
        assert ok, evidence
        assert "financial-statement schema" in evidence["per_field"]["inventory"]["not_applicable"]

        sidecar = os.path.join(work, "verified-dashboard-data.json")
        value = json.load(open(sidecar))
        value["financials"]["revenue"][-1] = 0.0
        write_json(sidecar, value)
        ok, evidence = iv.verify_period_integrity(REQ["REQ-062"], "<html></html>")
        assert not ok and any(
            x.get("code") == "PERIOD_VALUE_PAIR_MISMATCH" and x.get("field") == "revenue"
            for x in evidence["failures"]
        ), evidence


if __name__ == "__main__":
    test_req022_old_period_and_mutation()
    print("✓ REQ-022 old-period baseline + mutation")
    test_req059_zero_same_year_rounding_and_mutation()
    print("✓ REQ-059 zero/year/rounding baseline + mutation")
    test_req062_financial_schema_inventory_na_and_zero_mutation()
    print("✓ REQ-062 financial inventory N/A + zero mutation")
    print("✅ 3/3 Phase A wave 3 focused tests PASS")
