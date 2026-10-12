#!/usr/bin/env python3
"""boot/nixos-handoff.sh with fake commands: not requested -> returns 0 silently; requested but no server -> fails fast, cleans up and returns 1 (recovery shell stays)."""
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "nixos-handoff.sh"


def run(cmdline, fake_wget_ok=False, extra=None):
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "bin").mkdir()
        for name, body in {
            "wget": "exit 0" if fake_wget_ok else "exit 1",
            "sleep": "exit 0",
            "umount": "exit 0",
            "losetup": "exit 0",
            "mount": "exit 1",           # the tmpfs mount fails: exercises the cleanup path
        }.items():
            f = d / "bin" / name
            f.write_text("#!/bin/sh\n" + body + "\n")
            f.chmod(0o755)
        cl = d / "cmdline"
        cl.write_text(cmdline)
        env = {"PATH": f"{d / 'bin'}:/usr/bin:/bin", "CMDLINE": str(cl), "WORK": str(d / "work"), "LOG": str(d / "log"), "TIMEOUT_SECS": "3"}
        env.update(extra or {})
        r = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
        log = (d / "log").read_text() if (d / "log").exists() else ""
        return r, log


class HandoffTests(unittest.TestCase):
    def test_not_requested_does_nothing(self):
        r, log = run("console=tty0 loglevel=8")
        self.assertEqual((r.returncode, r.stdout, r.stderr, log), (0, "", "", ""))

    def test_unreachable_server_returns_failure_and_keeps_the_debug_shell(self):
        r, log = run("console=tty0 j81.nixos=http://172.16.42.2:8000")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("requested: http://172.16.42.2:8000/", log + r.stderr)
        self.assertIn("FAILED: no answer", r.stderr)
        self.assertNotIn("switching root", r.stderr)
        self.assertIn("staying in the debug initramfs", r.stderr)

    def test_failure_after_the_server_answers_is_clean_too(self):
        r, _ = run("j81.nixos=http://x/", fake_wget_ok=True)   # wget "succeeds" with empty output: bad toplevel
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAILED", r.stderr)

    def test_no_losetup_show_option_busybox_lacks_it(self):
        self.assertNotIn("losetup -f --show", SCRIPT.read_text())

    def test_sourcing_only_defines_functions(self):
        r = subprocess.run(["sh", "-c", f". {SCRIPT}; type nixos_handoff >/dev/null && echo defined"], env={"PATH": os.environ["PATH"]}, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "defined"))      # sourcing must not run anything or exit the caller

    def test_script_never_touches_the_network_for_private_files(self):
        text = SCRIPT.read_text()
        step5 = text.split("# 5.")[1].split("exit 0")[0]
        self.assertNotIn("wget", step5)                       # private files are only copied from this initramfs
        self.assertIn("never from the network", text)


if __name__ == "__main__":
    unittest.main()
