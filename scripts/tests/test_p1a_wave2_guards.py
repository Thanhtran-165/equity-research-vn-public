#!/usr/bin/env python3
"""Offline regression for P1-A wave 2 year binding and false-positive guards."""
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/independent_verifier.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("p1a_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def staging(module, files, html):
    work = Path(tempfile.mkdtemp(prefix="p1a_wave2_"))
    for rel, value in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    report = work / "TST_Complete_Report.html"
    report.write_text(html, encoding="utf-8")
    module.REPORT = str(report)
    module.TICKER = "TST"
    return report


def expect(name, got, expected=True):
    passed, evidence = got
    assert passed is expected, f"{name}: passed={passed}, evidence={evidence}"


def main():
    v = load_verifier()

    # REQ-023: latest available fiscal year, not hard-coded 2025.
    html = '<script>const DATA={"years":[2022,2023,2024],"totalAssets":[90,95,100],"equity":[30,35,40]};</script>'
    report = staging(v, {"data/balance_sheet.json": {
        "Total Assets": {"2022": 90e9, "2023": 95e9, "2024": 100e9},
        "Owner's Equity": {"2022": 30e9, "2023": 35e9, "2024": 40e9},
    }}, html)
    req23 = {"verification": {"data_file": "data/balance_sheet.json", "fields": [
        {"key": "Total Assets", "years": ["latest"], "divisor": 1e9, "tolerance_pct": 5},
        {"key": "Owner's Equity", "years": ["latest"], "divisor": 1e9, "tolerance_pct": 5},
    ]}}
    expect("REQ-023 latest", v.verify_data_accuracy(req23, report.read_text()))

    # REQ-024: bind each capex value to its year and retain null semantics.
    html = '<script>const DATA={"years":[2021,2022,2023],"capex":[1.0,null,3.0]};</script>'
    report = staging(v, {"data/cash_flow.json": {
        "Purchases of fixed assets and other long term assets": {"2021": -1e9, "2022": None, "2023": -3e9}
    }}, html)
    req24 = {"verification": {"data_file": "data/cash_flow.json", "capex_key": "Purchases of fixed assets and other long term assets", "tolerance_pct": 10}}
    expect("REQ-024 aligned", v.verify_capex_accuracy(req24, report.read_text()))
    expect("REQ-024 mutation", v.verify_capex_accuracy(req24, report.read_text().replace("3.0", "9.0")), False)

    # REQ-033/034: digits in ticker A32 are not metric claims.
    fin = {"revenue_ty": {"2025": 777.8}, "npatmi_ty": {"2025": 50.9}, "eps_vnd": {"2025": 6011.0}}
    html = ('<section id="sec-exec">Doanh thu A32 năm 2025 đạt 777.8 tỷ VND; EPS năm 2025 đạt 6011 VND.</section>'
            '<section id="sec-biz">Doanh thu A32 năm 2025 đạt 777.8 tỷ VND.</section>'
            '<script>const DATA={"years":[2025],"revenue":[777.8],"netProfit":[50.9],"eps":[6011]};</script>')
    report = staging(v, {"data/financials.json": fin}, html)
    expect("REQ-033 ticker digits", v.verify_cross_section_consistency({}, report.read_text()))
    expect("REQ-034 ticker digits", v.verify_temporal_alignment({"verification": {"data_file": "data/financials.json"}}, report.read_text()))

    # REQ-061: preserve negative signs; whole-billion market-cap rounding is bounded.
    fin = {"revenue_ty": {"2025": 100.0}, "npatmi_ty": {"2025": -10.0}, "equity_ty": {"2025": 200.0},
           "overview": {"current_price": 1000.0, "issue_share": 4_400_000.0}}
    bs = {"Total Assets": {"2025": 400e9}}
    html = '<section id="sec-exec">ROE năm 2025 -5.0%; ROA -2.5%; vốn hóa 4 tỷ.</section>'
    report = staging(v, {"data/financials.json": fin, "data/balance_sheet.json": bs}, html)
    expect("REQ-061 signs and rounding", v.verify_derived_metrics_recompute({"verification": {"tolerance_pct": 5}}, report.read_text()))

    # REQ-060: a multiple printed to two decimals gets half-step tolerance.
    fin = {"eps_vnd": {"2025": 1000.0}, "equity_ty": {"2025": 10.0},
           "npatmi_ty": {"2025": 1.0}, "overview": {"current_price": 100.0, "issue_share": 1_000_000.0}}
    html = '<section id="sec-valuation">P/E 0.10×; P/B 0.01×</section><section id="sec-hero">vốn hóa 0 tỷ</section>'
    report = staging(v, {"data/financials.json": fin}, html)
    expect("REQ-060 display rounding", v.verify_internal_identity({"verification": {"tolerance_pct": 5}}, report.read_text()))

    # REQ-060: year binding follows the latest common artifact year, never 2025 by fiat.
    fin = {"eps_vnd": {"2024": 900.0, "2026": 2000.0},
           "equity_ty": {"2024": 9.0, "2026": 20.0},
           "npatmi_ty": {"2024": 0.9, "2026": 2.0},
           "overview": {"current_price": 4000.0, "issue_share": 10_000_000.0}}
    html = ('<section id="sec-valuation">P/E 2.00×; P/B 2.00×</section>'
            '<section id="sec-hero">vốn hóa 40 tỷ</section>')
    report = staging(v, {"data/financials.json": fin}, html)
    passed, evidence = v.verify_internal_identity({"verification": {"tolerance_pct": 5}}, report.read_text())
    assert passed, evidence
    assert evidence["financial_year"] == "2026", evidence

    # REQ-068: required keys remain mandatory, but semantic N/A is valid.
    schema_dir = Path(tempfile.mkdtemp(prefix="p1a_schema_"))
    (schema_dir / "task-state.schema.json").write_text((ROOT / "task-state.schema.json").read_text())
    v.SKILL_DIR = str(schema_dir)
    phases = {
        "phase0_sponsor": {"status": "completed", "result": {"investment_amount": None, "fiscal_year_type": "calendar"}},
        "phase1_data": {"status": "completed", "result": {"data_source": "sponsor", "split_audit": {"ok": True}}},
        "phase2_fundamental": {"status": "completed", "result": {"eps": -1, "roe": -1, "cagr": None}},
        "phase3_valuation": {"status": "completed", "result": {"targets": {"base": 1}, "pe": None, "pb": None}},
        "phase4a_tech_active": {"status": "completed", "result": {"tech_score": 0, "verdict": "NEUTRAL"}},
        "phase4b_tech_profile": {"status": "completed", "result": {"archetype": "NEUTRAL"}},
        "phase5_news": {"status": "completed", "result": {"sentiment": {"neutral": 0}}},
        "phase6_dashboard": {"status": "completed", "result": {"artifact_path": "x.html"}},
    }
    report = staging(v, {".task-state/task-state.json": {"ticker": "TST", "phases": phases}}, "<html></html>")
    expect("REQ-068 semantic N/A", v.verify_phase_completion({}, report.read_text()))
    del phases["phase3_valuation"]["result"]["pe"]
    report = staging(v, {".task-state/task-state.json": {"ticker": "TST", "phases": phases}}, "<html></html>")
    expect("REQ-068 missing key", v.verify_phase_completion({}, report.read_text()), False)

    # REQ-036: explicit N/A is valid; a numeric mutation remains checkable.
    fin = {"revenue_ty": {"2023": -1.0, "2024": 2.0}, "npatmi_ty": {"2023": 1.0, "2024": 2.0}}
    report = staging(v, {"data/financials.json": fin}, "<section id='sec-exec'>CAGR doanh thu N/A — không tính.</section>")
    expect("REQ-036 explicit N/A", v.verify_cagr_recompute({"verification": {"data_file": "data/financials.json", "fields": ["revenue_ty"], "tolerance_pct": 2}}, report.read_text()))

    # REQ-063: ticker DCF is an entity, not automatically a DCF-method claim.
    v.TICKER = "DCF"
    ts = {"phases": {"phase3_valuation": {"result": {"dcf_per_share": None}}}}
    report = staging(v, {".task-state/task-state.json": ts}, "<section id='sec-valuation'>Định giá DCF theo P/B.</section>")
    v.TICKER = "DCF"
    expect("REQ-063 ticker acronym", v.verify_valuation_methods({"verification": {"methods": ["dcf_per_share"]}}, report.read_text()))

    # REQ-063: Graham uses the latest common artifact year rather than 2025.
    v.TICKER = "TST"
    graham = (22.5 * 2000.0 * 2000.0) ** 0.5
    ts = {"phases": {"phase3_valuation": {"result": {"graham_number": graham}}}}
    fin = {"eps_vnd": {"2024": 900.0, "2026": 2000.0},
           "equity_ty": {"2024": 9.0, "2026": 20.0},
           "overview": {"issue_share": 10_000_000.0}}
    report = staging(v, {".task-state/task-state.json": ts, "data/financials.json": fin},
                     "<section id='sec-valuation'>Số Graham được đối chiếu.</section>")
    passed, evidence = v.verify_valuation_methods({"verification": {"methods": ["graham_number"]}}, report.read_text())
    assert passed, evidence
    assert evidence["graham_year"] == "2026", evidence

    print("OK P1-A wave2: year binding, N/A semantics, signed metrics, rounding and mutations")


if __name__ == "__main__":
    main()
