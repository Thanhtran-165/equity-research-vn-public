#!/usr/bin/env python3
"""Offline regression and negative mutations for REQ-076."""
import copy
import importlib.util
import json
import math
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/independent_verifier.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("req076_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_FIN = {
    "overview": {"current_price": 10000.0, "issue_share": 100_000_000.0},
    "eps_vnd": {"2024": 1000.0, "2025": 2000.0},
    "equity_ty": {"2024": 800.0, "2025": 1000.0},
}
BASE_DATA = {"pe": 5.0, "pb": 1.0}


def write_case(fin=None, sidecar=None, html_data=None, include_sidecar=True,
               include_data=True):
    work = Path(tempfile.mkdtemp(prefix="req076_"))
    (work / "data").mkdir()
    (work / "data/financials.json").write_text(json.dumps(fin or BASE_FIN))
    if include_sidecar:
        (work / "verified-dashboard-data.json").write_text(
            json.dumps(BASE_DATA if sidecar is None else sidecar)
        )
    data = BASE_DATA if html_data is None else html_data
    script = f"<script>const DATA = {json.dumps(data)};</script>" if include_data else ""
    report = work / "TST_Complete_Report.html"
    report.write_text(f"<html>{script}</html>")
    return work, report


def verify(module, **kwargs):
    _work, report = write_case(**kwargs)
    module.REPORT = str(report)
    module.TICKER = "TST"
    return module.verify_data_scalar_accuracy({}, report.read_text())


def require(module, name, expected, **kwargs):
    passed, evidence = verify(module, **kwargs)
    assert passed is expected, f"{name}: passed={passed}, evidence={evidence}"


def main():
    v = load_verifier()
    require(v, "baseline", True)
    require(v, "sidecar PE mutation", False, sidecar={"pe": 999.99, "pb": 1.0})
    require(v, "HTML PE mutation", False, html_data={"pe": 999.99, "pb": 1.0})
    require(v, "sidecar PB mutation", False, sidecar={"pe": 5.0, "pb": 999.99})
    require(v, "missing sidecar", False, include_sidecar=False)
    require(v, "missing HTML DATA", False, include_data=False)
    require(v, "missing scalar", False, sidecar={"pb": 1.0})

    fin = copy.deepcopy(BASE_FIN)
    fin["overview"]["current_price"] = None
    require(v, "missing source price", False, fin=fin)

    fin = copy.deepcopy(BASE_FIN)
    fin["eps_vnd"]["2025"] = -100.0
    require(v, "negative PE is not N/A", False, fin=fin,
            sidecar={"pe": -5.0, "pb": 1.0}, html_data={"pe": -5.0, "pb": 1.0})

    fin = copy.deepcopy(BASE_FIN)
    fin["equity_ty"]["2025"] = -100.0
    require(v, "negative PB is not N/A", False, fin=fin,
            sidecar={"pe": 5.0, "pb": -1.0}, html_data={"pe": 5.0, "pb": -1.0})

    fin = copy.deepcopy(BASE_FIN)
    fin["overview"]["issue_share"] = None
    require(v, "missing shares", False, fin=fin)
    require(v, "string scalar", False, sidecar={"pe": "5.0", "pb": 1.0})
    require(v, "non-finite scalar", False, sidecar={"pe": math.nan, "pb": 1.0})

    # Values are rendered at two decimals: half a display unit is legitimate
    # rounding, but moving a full cent remains a detectable mutation.
    fin = copy.deepcopy(BASE_FIN)
    fin["overview"]["current_price"] = 300.0
    fin["equity_ty"]["2025"] = 1147.5  # BVPS=11,475; expected PB≈0.02614
    rounded = {"pe": 0.15, "pb": 0.03}
    require(v, "small PB legitimate rounding", True, fin=fin,
            sidecar=rounded, html_data=rounded)
    require(v, "small PB full-cent mutation", False, fin=fin,
            sidecar={"pe": 0.15, "pb": 0.04}, html_data=rounded)

    fin = copy.deepcopy(BASE_FIN)
    fin["overview"]["current_price"] = 100.0
    fin["eps_vnd"]["2025"] = 1870.0  # expected PE≈0.05348
    rounded = {"pe": 0.05, "pb": 0.01}
    require(v, "small PE legitimate rounding", True, fin=fin,
            sidecar=rounded, html_data=rounded)
    require(v, "small PE full-cent mutation", False, fin=fin,
            sidecar={"pe": 0.06, "pb": 0.01}, html_data=rounded)

    fin = copy.deepcopy(BASE_FIN)
    fin["eps_vnd"]["2025"] = -100.0
    require(v, "valid PE N/A", True, fin=fin,
            sidecar={"pe": None, "pb": 1.0}, html_data={"pe": 0, "pb": 1.0})
    print("OK REQ-076: baseline + fail-closed/N-A/rounding mutations")


if __name__ == "__main__":
    main()
