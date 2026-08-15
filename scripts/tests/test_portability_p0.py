#!/usr/bin/env python3
"""Guard ba P0 portability trước khi public."""

import sys
import unittest
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


class PortabilityP0Tests(unittest.TestCase):
    def test_builder_uses_current_interpreter_and_relative_verifier(self):
        text = (ROOT / "scripts/build_report.py").read_text(encoding="utf-8")
        self.assertIn("[sys.executable, verifier_path", text)
        self.assertIn("os.path.join(SKILL_DIR, 'scripts', 'independent_verifier.py')", text)
        self.assertNotIn("~/.zcode/skills/equity-research-vn/scripts/independent_verifier.py", text)
        hook = (ROOT / "scripts/hooks/predeploy-gate.sh").read_text(encoding="utf-8")
        self.assertIn('EQUITY_PYTHON', hook)
        self.assertIn('$HOME/.venv/equity-research-vn/bin/python', hook)

    def test_req002_no_longer_counts_api_dataframe_rows(self):
        reqs = yaml.safe_load((ROOT / "requirements.yaml").read_text(encoding="utf-8"))["requirements"]
        req1 = next(item for item in reqs if item["id"] == "REQ-001")
        req = next(item for item in reqs if item["id"] == "REQ-002")
        self.assertEqual(req1["verification"]["method"], "sponsor_import_check")
        self.assertEqual(req["verification"]["method"], "sponsor_period_check")

    def test_builder_has_actionable_sponsor_error(self):
        text = (ROOT / "scripts/build_report.py").read_text(encoding="utf-8")
        self.assertIn("except SponsorDependencyError as e", text)
        self.assertIn("sys.exit(2)", text)

    def test_statement_adapter_is_covered_by_freeze_hash(self):
        adapter = ROOT / "scripts/statement_adapter.py"
        expected = hashlib.sha256(adapter.read_bytes()).hexdigest()
        hash_file = (ROOT / ".verifier-hash").read_text(encoding="utf-8")
        self.assertIn(f"statement_adapter_sha256={expected}", hash_file)


if __name__ == "__main__":
    unittest.main()
