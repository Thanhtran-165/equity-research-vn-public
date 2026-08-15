#!/usr/bin/env python3
"""Chặn file sinh, file lớn và dữ liệu cục bộ trước khi public/push."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024

FORBIDDEN_PARTS = {
    ".task-state", "__pycache__", ".next", "node_modules", "evidence",
    "screenshots", "work_p0", "logs", "cache", "tmp", "temp",
}
FORBIDDEN_NAMES = {
    "gate-log.jsonl", "result.json", "verified-dashboard-data.json",
}
FORBIDDEN_SUFFIXES = {
    ".bak", ".bak2", ".backup", ".log", ".db", ".sqlite", ".sqlite3", ".duckdb",
}
TEXT_SUFFIXES = {
    ".py", ".js", ".sh", ".md", ".yaml", ".yml", ".json", ".html", ".css", ".txt",
}
TEXT_NAMES = {"SKILL.md", "README.md", "LICENSE", "VERSION", ".verifier-hash", ".gitignore"}
FORBIDDEN_TEXT = {
    "personal_home_path": re.compile("/" + r"Users/[A-Za-z0-9._-]+/"),
    "codex_skill_path": re.compile(r"\." + "codex/skills/equity-research-vn"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / raw.decode() for raw in output.split(b"\0") if raw]


def main() -> int:
    issues: list[str] = []
    files = tracked_files()
    for path in files:
        rel = path.relative_to(ROOT)
        if any(part in FORBIDDEN_PARTS for part in rel.parts):
            issues.append(f"forbidden path: {rel}")
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            issues.append(f"forbidden artifact: {rel}")
        if path.is_file() and path.stat().st_size > MAX_BYTES:
            issues.append(f"file >5 MiB: {rel}")
        if not path.is_file() or not (path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append(f"text file is not UTF-8: {rel}")
            continue
        for label, pattern in FORBIDDEN_TEXT.items():
            if pattern.search(text):
                issues.append(f"{label}: {rel}")

    if issues:
        print("PUBLIC GUARD: FAIL")
        for issue in sorted(set(issues)):
            print(f"- {issue}")
        return 1
    print(f"PUBLIC GUARD: PASS ({len(files)} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
