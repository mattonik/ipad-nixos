#!/usr/bin/env python3
"""boot/power-diag.sh against a fake sysfs tree and a fake i2ctransfer (host test, read-only tool)."""
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "power-diag.sh"

FAKE_I2C = """#!/bin/sh
# args: -f -y 0 w2@0x3c HI LO rN@0x3c ; log every call so the test can prove only reads happened
echo "$@" >> "$I2C_LOG"
case "$5$6" in
  0x040xc0) echo 0x4a ;;
  0x040xcf) echo 0x3c ;;
  0x040xc6) echo 0x3c ;;
  0x040xc7) echo 0x3f ;;
  0x000x10) echo 0x04 ;;
  0x000x60) echo 0x0f 0x03 0x62 0x20 0x7e 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x03 ;;
  *) echo 0x00 ;;
esac
"""


def make_tree(root, capacity=79, temp=325, current=231000):
    bat = root / "bat"
    chg = root / "chg"
    bat.mkdir()
    chg.mkdir()
    (bat / "uevent").write_text(
        f"POWER_SUPPLY_STATUS=Charging\nPOWER_SUPPLY_CAPACITY={capacity}\nPOWER_SUPPLY_VOLTAGE_NOW=4122000\n"
        f"POWER_SUPPLY_CURRENT_NOW={current}\nPOWER_SUPPLY_TEMP={temp}\nPOWER_SUPPLY_POWER_AVG=950000\n")
    (chg / "input_current_limit").write_text("2400000\n")
    (chg / "constant_charge_current_max").write_text("3000000\n")
    (root / "uptime").write_text("123.45 99.0\n")
    (root / "loadavg").write_text("0.57 0.17 0.06 1/90 400\n")
    (root / "policy.log").write_text("charging-policy: limit 2400000 uA (below 80%)\n")
    (root / "wlan").mkdir()
    (root / "wlan" / "operstate").write_text("up\n")
    bl = root / "backlight" / "panel"
    bl.mkdir(parents=True)
    (bl / "brightness").write_text("100\n")
    i2c = root / "i2ctransfer"
    i2c.write_text(FAKE_I2C)
    i2c.chmod(0o755)
    return {
        "CHG": str(chg), "BAT": str(bat), "I2CTRANSFER": str(i2c), "BACKLIGHT": str(root / "backlight"), "WLAN": str(root / "wlan"),
        "POLICY_LOG": str(root / "policy.log"), "UPTIME_FILE": str(root / "uptime"), "LOADAVG_FILE": str(root / "loadavg"),
        "I2C_LOG": str(root / "i2c.log"), "PATH": os.environ["PATH"],
    }


def run(env, *args):
    return subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)


class PowerDiagTests(unittest.TestCase):
    def test_snapshot_values(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d))
            r = run(env)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            for needle in ("Charging, 79 %, 4122 mV, 231 mA", "battery power     952 mW", "input limit       2400 mA (PMIC 0x04c0 = 0x4a; USB input suspend bit 1)",
                           "max charge curr   3000 mA (sysfs; PMIC 0x04cf = 0x3c, ceiling 3000 mA)", "charge programmed 3000 mA (PMIC 0x04c6 = 0x3c, 50 mA/count); hardware cap 3150 mA (0x04c7 = 0x3f)", "USB power limited bit 1", "VBUS current      n/a", "would choose target (2400 mA)",
                           "last log: charging-policy: limit 2400000 uA", "load 0.57, backlight 100, wlan0 up"):
                self.assertIn(needle, out)

    def test_only_reads_reach_the_pmic(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d))
            run(env)
            calls = pathlib.Path(env["I2C_LOG"]).read_text().splitlines()
            self.assertTrue(calls)
            for c in calls:
                self.assertRegex(c, r"^-f -y 0 w2@0x3c 0x[0-9a-f]{2} 0x[0-9a-f]{2} r\d+@0x3c$")  # one 2-byte address write, then a read: never a data write

    def test_policy_view_backoff(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d), capacity=85)
            self.assertIn("backoff (500 mA: capacity 85% >= 80%)", run(env).stdout)
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d), temp=430)
            self.assertIn("temperature 43.0 C >= 42 C", run(env).stdout)

    def test_log_mode_csv(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d))
            out = pathlib.Path(d) / "log.csv"
            r = run(env, "log", "-i", "0", "-n", "2", "-l", "wifi,off", "-o", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = out.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            header = lines[0].split(",")
            self.assertEqual(len(lines[1].split(",")), len(header))
            self.assertEqual(lines[1].split(",")[1], "wifi_off")      # commas in the label cannot break the CSV
            self.assertIn("n/a", lines[1])
            run(env, "log", "-i", "0", "-n", "1", "-o", str(out))     # appending does not repeat the header
            self.assertEqual(len(out.read_text().splitlines()), 4)

    def test_missing_i2ctransfer_and_gauge(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d))
            env["I2CTRANSFER"] = ""
            env["BAT"] = str(pathlib.Path(d) / "nonexistent")
            out = run(env).stdout
            self.assertIn("note              no i2ctransfer found", out)
            self.assertIn("backoff (500 mA: gauge reading unavailable)", out)

    def test_bad_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            env = make_tree(pathlib.Path(d))
            self.assertEqual(run(env, "log", "-i", "x").returncode, 2)
            self.assertEqual(run(env, "bogus").returncode, 2)
            self.assertEqual(run(env, "--help").returncode, 0)


if __name__ == "__main__":
    unittest.main()
