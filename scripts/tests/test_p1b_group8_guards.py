#!/usr/bin/env python3
"""Regression tự chứa cho các guard P1-B, không phụ thuộc artifact nội bộ."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_verifier(name: str, ticker: str, report: Path):
    old = sys.argv[:]
    sys.argv = [name, ticker, str(report)]
    try:
        spec = importlib.util.spec_from_file_location(
            name, ROOT / "scripts" / "independent_verifier.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.argv = old


def main() -> int:
    checks: list[tuple[bool, str]] = []

    # Builder phải giữ EPS reported=0; chỉ back-calc ô thực sự thiếu.
    source = (ROOT / "scripts" / "build_report.py").read_text()
    checks.append(("page_size=20" in source and "KBS_NEWS_SCHEMA" in source,
                   "KBS news giới hạn 20 và fail-closed khi schema lỗi"))
    tree = ast.parse(source)
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_resolve_eps_reported")
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "build_report.py", "exec"), namespace)
    got = namespace["_resolve_eps_reported"]([0.0, None], [False, True], [100.0, 100.0], 10.0)
    checks.append((got == [0.0, 10.0], f"EPS oracle: {got}"))

    with tempfile.TemporaryDirectory(prefix="p1b_public_") as tmp:
        work = Path(tmp)
        report = work / "TST_Complete_Report.html"
        report.write_text("<html><body><section id='sec-valuation'>Test</section></body></html>")
        verifier = load_verifier("verifier_public_p1b", "TST", report)

        # Claim vĩ mô/chức vụ không cite vẫn phải bị bắt.
        passed, _ = verifier.verify_macro_data_citation(
            {}, "<html><body>CPI tăng 4,5% trong năm.</body></html>"
        )
        checks.append((not passed, "mutation CPI macro không cite phải FAIL"))
        passed, _ = verifier.verify_management_claim(
            {}, "<html><body>CEO được bổ nhiệm trong năm nay.</body></html>"
        )
        checks.append((not passed, "mutation management không cite phải FAIL"))

        # Empty-news chỉ PASS khi fetch thành công và tươi; API error phải FAIL.
        digest = work / "news_digest.json"
        digest.write_text(json.dumps({
            "fetched_at": date.today().isoformat(), "fetch_status": "ok_empty",
            "provider": "KBS", "articles": [],
        }))
        passed, _ = verifier.verify_news_window({}, report.read_text())
        checks.append((passed, "news ok_empty tươi phải PASS"))
        digest.write_text(json.dumps({
            "fetched_at": date.today().isoformat(), "fetch_status": "error",
            "provider": "KBS", "articles": [],
        }))
        passed, _ = verifier.verify_news_window({}, report.read_text())
        checks.append((not passed, "news API error phải FAIL"))

    for ok, label in checks:
        print(("PASS" if ok else "FAIL"), label)
    return 0 if all(ok for ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
