#!/usr/bin/env python3
"""Regression tests cho task-state trong nhánh ``--reuse``."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from task_state_runtime import SponsorPeriodError, sponsor_period_count  # noqa: E402


class SponsorPeriodCountTests(unittest.TestCase):
    """Bắt lỗi reuse dùng ``D_raw=None`` thay vì ba CSV đã đóng băng."""

    @staticmethod
    def _write_csv(path: Path, rows: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["period", "value"])
            for index in range(rows):
                writer.writerow([f"P{index + 1}", index])

    def test_uses_minimum_row_count_across_three_sponsor_csvs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            source_pack = work / "source-pack"
            self._write_csv(source_pack / "income_statement_sponsor.csv", 44)
            self._write_csv(source_pack / "balance_sheet_sponsor.csv", 42)
            self._write_csv(source_pack / "cash_flow_sponsor.csv", 43)

            self.assertEqual(sponsor_period_count(work), 42)

    def test_missing_sponsor_csv_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            source_pack = work / "source-pack"
            self._write_csv(source_pack / "income_statement_sponsor.csv", 44)
            self._write_csv(source_pack / "balance_sheet_sponsor.csv", 42)

            with self.assertRaisesRegex(SponsorPeriodError, "cash_flow_sponsor.csv"):
                sponsor_period_count(work)


if __name__ == "__main__":
    unittest.main()
