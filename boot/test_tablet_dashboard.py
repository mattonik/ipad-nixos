#!/usr/bin/env python3
"""Run tablet-dashboard.sh against a fake sysfs tree; check it stays read-only."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).parent
SCRIPT = HERE / "tablet-dashboard.sh"
STATUS = HERE / "tablet-status.sh"


def build_tree(root, temp="313", capacity="62"):
    bat = root / "class/power_supply/bq27545-battery"
    chg = root / "class/power_supply/j81-d2207-charger"
    bat.mkdir(parents=True); chg.mkdir(parents=True)
    (root / "class/net/usb0").mkdir(parents=True)
    (bat / "uevent").write_text(
        f"POWER_SUPPLY_CAPACITY={capacity}\nPOWER_SUPPLY_STATUS=Charging\n"
        f"POWER_SUPPLY_VOLTAGE_NOW=4000000\nPOWER_SUPPLY_CURRENT_NOW=500000\nPOWER_SUPPLY_TEMP={temp}\n")
    (chg / "input_current_limit").write_text("2400000\n")
    (chg / "online").write_text("1\n")
    (root / "class/net/usb0/carrier").write_text("1\n")
    (root / "uptime").write_text("12.50 3.1\n")


def run(root, *args, **extra):
    env = dict(os.environ, SYSFS=str(root), PROCFS=str(root),
               TABLET_STATUS=f"sh {STATUS}", POLICY_LOG=str(root / "policy.log"),
               DROPBEAR_PID=str(root / "dropbear.pid"), **extra)
    return subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def snapshot(root):
    return sorted((p.relative_to(root).as_posix(), p.read_bytes() if p.is_file() else None)
                  for p in root.rglob("*"))


class DashboardTests(unittest.TestCase):
    def test_once_renders_all_sections(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_tree(root)
            (root / "policy.log").write_text("a\nb\nc\nlimit 2400000 uA (temp 313 deciC)\n")
            out = run(root, "--once").stdout
            for text in ("tablet dashboard", "== battery ==", "capacity: 62%", "temperature: 31.3 C",
                         "input_current_limit: 2400 mA", "== services ==", "ssh (dropbear):",
                         "== charging policy log (last 3) ==", "limit 2400000 uA"):
                self.assertIn(text, out)
            self.assertNotIn("\na\n", out)  # only the last three log lines

    def test_missing_files_degrade_to_na_and_never_fail(self):
        with tempfile.TemporaryDirectory() as d:
            proc = run(Path(d), "--once")
            self.assertEqual(proc.returncode, 0)
            self.assertIn("capacity: n/a", proc.stdout)
            self.assertIn("ssh (dropbear): not running", proc.stdout)
            self.assertIn("n/a", proc.stdout.split("charging policy log")[1])

    def test_dropbear_pid_detection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_tree(root)
            (root / "dropbear.pid").write_text(f"{os.getpid()}\n")
            self.assertIn("ssh (dropbear): running", run(root, "--once").stdout)

    def test_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_tree(root)
            self.assertEqual(run(root, "--help").returncode, 0)
            for bad in (("--interval",), ("--interval", "x"), ("--bogus",)):
                self.assertEqual(run(root, *bad).returncode, 2, bad)

    def test_does_not_write_anything(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_tree(root)
            before = snapshot(root)
            run(root, "--once")
            self.assertEqual(before, snapshot(root))

    def test_source_has_no_control_or_write_actions(self):
        text = SCRIPT.read_text() + STATUS.read_text()
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        for forbidden in ("i2cset", "i2ctransfer", "devmem", "touch-diag", "btattach", "dropbear ",
                          "telnetd", "mount", "dd ", "mkfs", "reboot", "poweroff", "gpioset",
                          "charging-policy ", "input_current_limit ="):
            self.assertNotIn(forbidden, code, forbidden)
        # The only redirections allowed are to the null device or stderr merge.
        for line in code.splitlines():
            for target in re.findall(r"\d?>>?\s*([^\s;|)]+)", line):
                self.assertIn(target, {"/dev/null", "&1", "&2", '"$frame"'}, line)

    def test_interactive_loop_restores_cursor_and_is_never_autostarted(self):
        text = SCRIPT.read_text()
        self.assertIn("trap 'printf \"\\033[?25h", text)
        hook = (HERE / "ssh-stage1.sh").read_text()
        self.assertNotIn("tablet-dashboard", hook)


if __name__ == "__main__":
    unittest.main()
