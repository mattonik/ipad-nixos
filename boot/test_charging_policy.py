#!/usr/bin/env python3
"""Run charging-policy.sh against a fake sysfs tree (ONCE mode)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("charging-policy.sh")


class Env:
    def __init__(self, temp="313", writable=True):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.chg = root / "chg"
        self.bat = root / "bat"
        self.chg.mkdir(); self.bat.mkdir()
        (self.chg / "input_current_limit").write_text("100000\n")
        (self.chg / "input_current_limit").chmod(0o644 if writable else 0o444)
        self.set_temp(temp)

    def set_temp(self, temp):
        text = "POWER_SUPPLY_CAPACITY=50\n"
        if temp is not None:
            text += f"POWER_SUPPLY_TEMP={temp}\n"
        (self.bat / "uevent").write_text(text)

    def run(self, **extra):
        env = dict(os.environ, CHG=str(self.chg), BAT=str(self.bat), ONCE="1",
                   WAIT_SECS="1", **extra)
        proc = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
        return proc

    def limit(self):
        return (self.chg / "input_current_limit").read_text().strip()


class ChargingPolicyTests(unittest.TestCase):
    def test_cool_raises_to_target(self):
        e = Env("313")
        self.assertEqual(e.run().returncode, 0)
        self.assertEqual(e.limit(), "2400000")

    def test_hot_uses_safe_tier(self):
        e = Env("425")
        e.run()
        self.assertEqual(e.limit(), "500000")

    def test_unreadable_temperature_is_safe_never_target(self):
        for temp in (None, "x", "-"):
            e = Env(temp)
            e.run()
            self.assertEqual(e.limit(), "500000", temp)

    def test_missing_sysfs_leaves_limit_and_exits_nonzero(self):
        e = Env("313", writable=False)
        if os.access(e.chg / "input_current_limit", os.W_OK):
            self.skipTest("running as root; permissions not enforced")
        proc = e.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(e.limit(), "100000")

    def test_only_touches_input_current_limit(self):
        e = Env("313")
        before = {p.name for p in Path(e.dir.name).rglob("*")}
        e.run()
        self.assertEqual(before, {p.name for p in Path(e.dir.name).rglob("*")})


if __name__ == "__main__":
    unittest.main()
