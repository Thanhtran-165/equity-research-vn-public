#!/usr/bin/env python3
"""Offline regression for REQ-025 narrative PE/PB and N/A semantics."""
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/independent_verifier.py"
REQ = {
    "verification": {
        "formulas": [
            {"name": "PE", "tolerance_pct": 2},
            {"name": "PB", "tolerance_pct": 2},
        ]
    }
}


def load_verifier():
    spec = importlib.util.spec_from_file_location("req025_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(module, fin, text):
    work = Path(tempfile.mkdtemp(prefix="req025_"))
    (work / "data").mkdir()
    (work / "data/financials.json").write_text(json.dumps(fin))
    report = work / "TST_Complete_Report.html"
    report.write_text(
        f'<section id="sec-valuation">{text}</section>'
        f'<section id="sec-hero">{text}</section>'
        f'<section id="sec-exec">{text}</section>'
    )
    module.REPORT = str(report)
    module.TICKER = "TST"
    return module.verify_valuation_recompute(REQ, report.read_text())


def expect(module, name, expected, fin, text):
    passed, evidence = run(module, fin, text)
    assert passed is expected, f"{name}: passed={passed}, evidence={evidence}"


def main():
    v = load_verifier()
    positive = {
        "overview": {"current_price": 10000.0, "issue_share": 100_000_000.0},
        "eps_vnd": {"2024": 1000.0, "2025": 2000.0},
        "equity_ty": {"2024": 800.0, "2025": 1000.0},
    }
    expect(v, "positive baseline", True, positive, "P/E 5.00×; P/B 1.00×")
    expect(v, "positive mutation", False, positive, "P/E 6.00×; P/B 1.00×")

    loss = {
        "overview": {"current_price": 500.0, "issue_share": 50_000_000.0},
        "eps_vnd": {"2024": 100.0, "2025": -3105.0},
        "equity_ty": {"2024": 20.0, "2025": -989.5},
    }
    expect(v, "loss explicit N/A", True, loss, "P/E N/A; P/B N/A")
    expect(v, "loss missing N/A", False, loss, "Định giá chưa cập nhật")
    expect(v, "loss negative multiple", False, loss, "P/E -0.16×; P/B -0.03×")

    tiny = {
        "overview": {"current_price": 300.0, "issue_share": 100_000_000.0},
        "eps_vnd": {"2025": 2155.0},
        "equity_ty": {"2025": 1147.5},
    }
    expect(v, "tiny rounded baseline", True, tiny, "P/E 0.14×; P/B 0.03×")
    expect(v, "tiny full-cent mutation", False, tiny, "P/E 0.14×; P/B 0.04×")
    print("OK REQ-025: dynamic year, explicit N/A, rounding and mutations")


if __name__ == "__main__":
    main()
