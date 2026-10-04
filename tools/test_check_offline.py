#!/usr/bin/env python3
"""Check process failure/timeout reporting and assertion preservation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_offline


class RunnerTests(unittest.TestCase):
    def run_fixture(self, source, timeout=5):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fixture.py"
            script.write_text(source)
            return check_offline.execute("fixture", [str(script)], timeout)

    def test_failure_propagates_and_preserves_diagnostics(self):
        result = self.run_fixture("import sys; print('diagnostic'); sys.exit(7)")
        self.assertEqual(result.state, "FAIL")
        self.assertIn("diagnostic", result.detail)

    def test_success(self):
        self.assertEqual(self.run_fixture("print('ok')").state, "PASS")

    def test_assertions_stay_enabled(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "2"}):
            result = self.run_fixture("assert False, 'assertion active'")
        self.assertEqual(result.state, "FAIL")
        self.assertIn("assertion active", result.detail)

    def test_timeout_is_a_failure(self):
        result = self.run_fixture("import time; time.sleep(10)", timeout=0.1)
        self.assertEqual(result.state, "FAIL")
        self.assertIn("exceeded", result.detail)

    def test_dhd_inputs_must_be_supplied_together(self):
        for flag in ("--dhd-source", "--dhd-header"):
            with self.subTest(flag=flag):
                result = subprocess.run([sys.executable, str(check_offline.ROOT / "tools/check_offline.py"),
                                         flag, "/nonexistent/source-fixture"],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertIn("supply both --dhd-source and --dhd-header", result.stderr)
                self.assertNotIn("PASS:", result.stdout)


if __name__ == "__main__":
    unittest.main()
