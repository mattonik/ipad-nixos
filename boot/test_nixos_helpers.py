#!/usr/bin/env python3
"""boot/power-logger.sh and boot/backlight-idle.sh with fake commands (host tests)."""
import os
import pathlib
import subprocess
import tempfile
import unittest

B = pathlib.Path(__file__).resolve().parent


def sh(script, env, args=()):
    return subprocess.run(["sh", str(B / script), *args], env=env, capture_output=True, text=True, timeout=30)


class LoggerTests(unittest.TestCase):
    def fake_diag(self, d, rows_bytes=0):
        f = d / "power-diag"
        f.write_text('#!/bin/sh\necho "$@" >> "$CALLS"\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done\nhead -c %d /dev/zero | tr "\\\\0" x >> "$out"\n' % rows_bytes)
        f.chmod(0o755)
        return f

    def test_read_only_by_default_and_rotates(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            diag = self.fake_diag(d, rows_bytes=600)
            env = {"PATH": os.environ["PATH"], "POWER_DIAG": str(diag), "FILE": str(d / "p.csv"), "CALLS": str(d / "calls"), "MAX_BYTES": "1000", "MAX_ROUNDS": "3", "INTERVAL": "1"}
            r = sh("power-logger.sh", env)
            self.assertEqual(r.returncode, 0, r.stderr)
            calls = (d / "calls").read_text().splitlines()
            self.assertEqual(len(calls), 3)
            self.assertTrue(all("--vbus" not in c for c in calls))            # VBUS reads stay off
            self.assertTrue((d / "p.csv.old").exists())                         # rotated once it grew past MAX_BYTES

    def test_vbus_only_when_asked(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            diag = self.fake_diag(d)
            env = {"PATH": os.environ["PATH"], "POWER_DIAG": str(diag), "FILE": str(d / "p.csv"), "CALLS": str(d / "calls"), "MAX_ROUNDS": "1", "VBUS": "1"}
            sh("power-logger.sh", env)
            self.assertIn("--vbus", (d / "calls").read_text())


class BacklightTests(unittest.TestCase):
    def run_idle(self, activity):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            bl = d / "brightness"
            bl.write_text("1627\n")
            ev = d / "event0"
            ev.write_bytes(b"\0" * 24 * 4 if activity else b"")        # a file with events never blocks; an empty one reads 0 bytes (dd fails the count)
            fake = d / "bin"
            fake.mkdir()
            (fake / "timeout").write_text('#!/bin/sh\nshift; "$@"\n')      # no waiting: run the command
            (fake / "timeout").chmod(0o755)
            hist = d / "hist"
            env = {"PATH": f"{fake}:{os.environ['PATH']}", "BL": str(bl), "EVENT": str(ev), "IDLE_SECS": "1", "DIM": "100", "MAX_LOOPS": "1"}
            r = subprocess.run(["sh", "-c", f'sh {B / "backlight-idle.sh"}; cat {bl} > {hist}'], env=env, capture_output=True, text=True, timeout=30)
            return r, hist.read_text().strip()

    def test_restores_brightness_on_exit(self):
        r, final = self.run_idle(activity=True)
        self.assertEqual((r.returncode, final), (0, "1627"))

    def test_missing_backlight_is_an_error(self):
        r = subprocess.run(["sh", str(B / "backlight-idle.sh")], env={"PATH": os.environ["PATH"], "BL": "/nonexistent/brightness"}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
