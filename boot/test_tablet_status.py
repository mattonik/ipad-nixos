#!/usr/bin/env python3
"""Run tablet-status against fake sysfs trees and prove it never writes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("tablet-status.sh")


def run(root):
    env = dict(os.environ, SYSFS=str(root), PROCFS=str(root))
    return subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True,
                          text=True, check=True).stdout


class TabletStatusTest(unittest.TestCase):
    def test_full_tree(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bat = root / "class/power_supply/bq27545-battery"
            chg = root / "class/power_supply/j81-d2207-charger"
            bat.mkdir(parents=True); chg.mkdir(parents=True)
            (root / "class/net/usb0").mkdir(parents=True)
            (bat / "uevent").write_text(
                "POWER_SUPPLY_CAPACITY=87\nPOWER_SUPPLY_STATUS=Charging\n"
                "POWER_SUPPLY_VOLTAGE_NOW=4123000\nPOWER_SUPPLY_CURRENT_NOW=-110000\n"
                "POWER_SUPPLY_TEMP=333\n")
            (chg / "input_current_limit").write_text("2400000\n")
            (chg / "online").write_text("1\n")
            (root / "class/net/usb0/carrier").write_text("1\n")
            (root / "uptime").write_text("5.25 3.1\n")
            before = sorted(p.relative_to(root) for p in root.rglob("*"))
            out = run(root)
            for line in ("capacity: 87%", "status: Charging", "voltage: 4123 mV",
                         "current: -110 mA", "temperature: 33.3 C",
                         "input_current_limit: 2400 mA", "carrier: 1"):
                self.assertIn(line, out)
            self.assertEqual(before, sorted(p.relative_to(root) for p in root.rglob("*")))

    def test_missing_tree_is_all_na(self):
        with tempfile.TemporaryDirectory() as d:
            out = run(Path(d))
            self.assertIn("capacity: n/a", out)
            self.assertIn("input_current_limit: n/a", out)

    def test_script_has_no_writes(self):
        text = SCRIPT.read_text()
        self.assertNotIn("i2cset", text)
        self.assertNotIn("i2ctransfer", text)


if __name__ == "__main__":
    unittest.main()
