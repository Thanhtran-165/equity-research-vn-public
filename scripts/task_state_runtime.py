#!/usr/bin/env python3
"""Tiện ích runtime cho task-state, dùng được ở cả fetch mới và ``--reuse``."""

import csv
from pathlib import Path


class SponsorPeriodError(RuntimeError):
    """Source-pack không đủ để xác định số kỳ theo chính sách min-3-CSV."""


SPONSOR_CSV_NAMES = (
    "income_statement_sponsor.csv",
    "balance_sheet_sponsor.csv",
    "cash_flow_sponsor.csv",
)


def sponsor_period_count(work_dir):
    """Trả số kỳ nhỏ nhất của ba CSV sponsor; thiếu/rỗng thì fail-closed."""

    source_pack = Path(work_dir) / "source-pack"
    counts = []
    for name in SPONSOR_CSV_NAMES:
        path = source_pack / name
        if not path.is_file():
            raise SponsorPeriodError(f"Thiếu source-pack/{name}; không thể xác định periods.")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            count = sum(1 for _ in csv.DictReader(handle))
        if count <= 0:
            raise SponsorPeriodError(f"source-pack/{name} rỗng; không thể xác định periods.")
        counts.append(count)
    return min(counts)
