#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_environment import SponsorDependencyError, raise_sponsor_dependency  # noqa: E402


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_missing_sponsor_message_is_actionable_and_fail_closed(self):
        try:
            raise_sponsor_dependency(ModuleNotFoundError("vnstock_data", name="vnstock_data"))
        except SponsorDependencyError as exc:
            text = str(exc)
        else:
            self.fail("phải raise SponsorDependencyError")
        self.assertIn("vnstock Sponsor", text)
        self.assertIn("README.md", text)
        self.assertIn("Không có fallback community", text)


if __name__ == "__main__":
    unittest.main()
