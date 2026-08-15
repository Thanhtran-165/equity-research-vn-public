#!/usr/bin/env python3
"""Durable regression for the hook's ANSI-safe fail-count parser."""
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks/predeploy-gate.sh"


def parse(text):
    result = subprocess.run(
        ["bash", str(HOOK), "--self-test-parser"], input=text,
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip())


def main():
    esc = "\x1b"
    assert parse(f"{esc}[0;31mREQ-021 FAIL{esc}[0m\n{esc}[31m2 requirement(s) failed{esc}[0m") == 2
    assert parse("All requirements passed") == 0
    assert parse("REQ-076 FAIL\n12 requirement(s) failed") == 12
    print("OK gate parser: ANSI fail=2, clean pass=0, multi-digit fail=12")


if __name__ == "__main__":
    main()
