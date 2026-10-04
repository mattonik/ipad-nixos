#!/usr/bin/env python3
"""Run charging-policy.sh against a fake sysfs tree (ONCE mode)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("charging-policy.sh")


class Env:
    def __init__(self, temp="313", capacity="50", writable=True):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.chg = root / "chg"
        self.bat = root / "bat"
        self.chg.mkdir(); self.bat.mkdir()
        (self.chg / "input_current_limit").write_text("100000\n")
        (self.chg / "input_current_limit").chmod(0o644 if writable else 0o444)
        self.set_battery(temp, capacity)

    def set_battery(self, temp, capacity):
        text = ""
        if capacity is not None:
            text += f"POWER_SUPPLY_CAPACITY={capacity}\n"
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

    def test_capacity_limit_is_safe_never_target(self):
        for capacity in ("80", "81", None, "x", "-"):
            e = Env(capacity=capacity)
            e.run()
            self.assertEqual(e.limit(), "500000", capacity)

        e = Env(capacity="79")
        e.run()
        self.assertEqual(e.limit(), "2400000")

    def test_negative_or_malformed_capacity_is_unreadable_not_target(self):
        for capacity in ("-5", "-", "5x", "1.5", " "):
            e = Env(capacity=capacity)
            e.run()
            self.assertEqual(e.limit(), "500000", repr(capacity))

    def test_capacity_boundary_and_full(self):
        for capacity, expected in (("79", "2400000"), ("80", "500000"), ("100", "500000"),
                                   ("255", "500000"), ("0", "2400000")):
            e = Env(capacity=capacity)
            e.run()
            self.assertEqual(e.limit(), expected, capacity)

    def test_either_limit_or_either_unreadable_backs_off(self):
        cases = (("425", "50"), ("313", "80"), (None, "50"), ("313", None), (None, None), ("425", "90"))
        for temp, capacity in cases:
            e = Env(temp, capacity)
            e.run()
            self.assertEqual(e.limit(), "500000", (temp, capacity))

    def test_cold_negative_temperature_is_valid(self):
        e = Env("-50", "50")
        e.run()
        self.assertEqual(e.limit(), "2400000")

    def test_hysteresis_latch_across_iterations(self):
        # One process, three iterations: 42.5 C (hot) -> 40.0 C (between the
        # thresholds, must stay latched safe) -> 38.0 C (cool, resume).
        e = Env("425", "50")
        root = Path(e.dir.name)
        queue, trace = root / "queue", root / "trace"
        queue.write_text("400\n380\n")
        fakebin = root / "bin"
        fakebin.mkdir()
        sleep = fakebin / "sleep"
        sleep.write_text(f"""#!/bin/sh
cat {e.chg}/input_current_limit >> {trace}
next=$(head -n 1 {queue})
sed 1d {queue} > {queue}.new && mv {queue}.new {queue}
printf 'POWER_SUPPLY_CAPACITY=50\\nPOWER_SUPPLY_TEMP=%s\\n' "$next" > {e.bat}/uevent
""")
        sleep.chmod(0o755)
        env = dict(os.environ, CHG=str(e.chg), BAT=str(e.bat), MAX_ITER="3", INTERVAL="0",
                   WAIT_SECS="1", PATH=f"{fakebin}:{os.environ['PATH']}")
        proc = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after_iterations_1_and_2 = trace.read_text().split()
        self.assertEqual(after_iterations_1_and_2, ["500000", "500000"])
        self.assertEqual(e.limit(), "2400000")

    def test_capacity_cap_releases_when_below_cap_again(self):
        e = Env("313", "80")
        root = Path(e.dir.name)
        queue, trace = root / "queue", root / "trace"
        queue.write_text("79\n")
        fakebin = root / "bin"
        fakebin.mkdir()
        sleep = fakebin / "sleep"
        sleep.write_text(f"""#!/bin/sh
cat {e.chg}/input_current_limit >> {trace}
next=$(head -n 1 {queue})
printf 'POWER_SUPPLY_CAPACITY=%s\\nPOWER_SUPPLY_TEMP=313\\n' "$next" > {e.bat}/uevent
""")
        sleep.chmod(0o755)
        env = dict(os.environ, CHG=str(e.chg), BAT=str(e.bat), MAX_ITER="2", INTERVAL="0",
                   WAIT_SECS="1", PATH=f"{fakebin}:{os.environ['PATH']}")
        subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, check=True)
        self.assertEqual(trace.read_text().split(), ["500000"])
        self.assertEqual(e.limit(), "2400000")

    def test_missing_sysfs_leaves_limit_and_exits_nonzero(self):
        e = Env("313", writable=False)
        if os.access(e.chg / "input_current_limit", os.W_OK):
            self.skipTest("running as root; permissions not enforced")
        proc = e.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(e.limit(), "100000")

    def test_already_correct_is_not_rewritten_and_drift_is_corrected(self):
        e = Env("313")
        (e.chg / "input_current_limit").write_text("2400000\n")
        self.assertNotIn("limit", e.run().stdout)
        (e.chg / "input_current_limit").write_text("1000000\n")  # external change
        e.run()
        self.assertEqual(e.limit(), "2400000")

    def test_between_thresholds_at_start_uses_target(self):
        e = Env("400")
        e.run()
        self.assertEqual(e.limit(), "2400000")

    def test_only_touches_input_current_limit(self):
        e = Env("313")
        before = {p.name for p in Path(e.dir.name).rglob("*")}
        e.run()
        self.assertEqual(before, {p.name for p in Path(e.dir.name).rglob("*")})


if __name__ == "__main__":
    unittest.main()
