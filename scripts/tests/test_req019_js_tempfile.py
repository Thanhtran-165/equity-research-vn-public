#!/usr/bin/env python3
"""Regression: concurrent REQ-019 checks must use unique, cleaned JS files."""
import concurrent.futures
import importlib.util
import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/independent_verifier.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("req019_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    v = load_verifier()
    v.TICKER = "TST"
    v.REPORT = "/tmp/TST_Complete_Report.html"
    seen = []

    def fake_run(cmd, _ticker, _report):
        path = shlex.split(cmd)[-1]
        assert os.path.exists(path), path
        assert "const marker" in Path(path).read_text()
        seen.append(path)
        return 0, ""

    v.run_command_safe = fake_run
    req = {"verification": {"command": "node --check $JS_FILE", "expect_exit": 0}}

    def check(index):
        return v.verify_command(req, f"<script>const marker = {index};</script>")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, range(32)))

    assert all(passed for passed, _evidence in results), results
    assert len(seen) == 32 and len(set(seen)) == 32, seen
    assert not any(os.path.exists(path) for path in seen), "temporary JS file leaked"
    print("OK REQ-019: 32 concurrent checks used unique, cleaned JS temp files")


if __name__ == "__main__":
    main()
