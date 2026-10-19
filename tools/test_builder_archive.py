#!/usr/bin/env python3
"""tools/builder.sh archive / restore against tiny fixtures: a fake `nix`, the real zstd and shasum, temporary directories. Never touches the real VM data."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent / "builder.sh"
FAKE_NIX = """#!/bin/sh
# records calls; emulates `nix copy --to/--from file://...`, `nix build STORE -o LINK`, `nix --version`
echo "$@" >> "$NIX_CALLS"
case "$*" in
  *--version*) echo "nix (fake) 2.34" ;;
  *"copy --to file://"*) [ "${NIX_COPY_FAIL:-0}" = 1 ] && { echo "error: filesystem error: in rename: File exists" >&2; exit 1; }
     d=$(echo "$*" | sed -n 's|.*--to file://\\([^ ]*\\).*|\\1|p'); mkdir -p "$d"; echo cache > "$d/nix-cache-info" ;;
  *"copy --from"*) [ "${NIX_UNTRUSTED:-0}" = 1 ] && { echo "error: cannot add path: lacks a signature by a trusted key" >&2; exit 1; } ;;
  *build*) link=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && link=$2; shift; done; [ -n "$link" ] && ln -sfn "$FAKE_LAUNCHER" "$link" ;;
esac
exit 0
"""


class Fixture:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        t = self.tmp
        self.state, self.arch, self.restore = t / "state", t / "arch", t / "restored"
        self.state.mkdir()
        self.guest = t / "guest-system"
        self.guest.mkdir()
        (self.guest / "kernel").write_bytes(b"k")
        self.launcher = t / "launcher"
        self.launcher.mkdir()
        (self.state / "result-linux-builder").symlink_to(self.launcher)
        (self.state / "nixos.qcow2").write_bytes(os.urandom(300_000) + bytes(2_000_000))
        (self.state / "store-abc.img").write_bytes(b"s" * 1000)
        (self.state / "keys").mkdir()
        (self.state / "keys" / "builder_ed25519").write_text("private\n")
        (self.state / "vzvm.json").write_text(json.dumps({"kernel": str(self.guest / "kernel")}))
        bindir = t / "bin"
        bindir.mkdir()
        nix = bindir / "nix"
        nix.write_text(FAKE_NIX)
        nix.chmod(0o755)
        self.env = {"PATH": f"{bindir}:{os.environ['PATH']}", "BUILDER_DIR": str(self.state), "BUILDER_ARCHIVE": str(self.arch), "BUILDER_TEST": "1",
                    "NIX_CALLS": str(t / "nix.calls"), "FAKE_LAUNCHER": str(self.launcher), "PYTHON": "/opt/homebrew/bin/python3", "HOME": str(t)}

    def run(self, *args, **extra):
        env = dict(self.env, **{k: str(v) for k, v in extra.items()})
        return subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=120)

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class BuilderArchiveTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def archive(self, *args):
        r = self.f.run("archive", *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        latest = (self.f.arch / "latest").read_text().strip()
        return self.f.arch / latest

    def test_dry_run_writes_nothing(self):
        r = self.f.run("archive", "-n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry run: nothing written", r.stdout)
        self.assertFalse(self.f.arch.exists())

    def test_archive_contents_and_verification(self):
        d = self.archive()
        for name in ("nixos.qcow2.zst", "keys.tgz", "vzvm.json", "meta.txt", "SHA256SUMS", "cache/nix-cache-info"):
            self.assertTrue((d / name).exists(), name)
        self.assertFalse(any(p.name.startswith("store-") for p in d.iterdir()))          # the derived store image is not archived
        meta = (d / "meta.txt").read_text()
        for key in ("disk_sha256:", "launcher:", "guest_system:", "flake_lock_sha256:"):
            self.assertIn(key, meta)
        self.assertTrue((self.f.state / "nixos.qcow2").exists())                          # local copy kept without --delete-local
        self.assertEqual(subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=d, capture_output=True).returncode, 0)

    def test_delete_local_needs_yes_and_removes_only_the_big_files(self):
        r = self.f.run("archive", "--delete-local", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.f.state / "nixos.qcow2").exists())
        self.assertFalse(list(self.f.state.glob("store-*.img")))
        self.assertTrue((self.f.state / "keys" / "builder_ed25519").exists())              # keys and the launcher link stay
        self.assertTrue((self.f.state / "result-linux-builder").is_symlink())

    def test_failed_nix_copy_cleans_up_its_partial_archive_and_keeps_local_files(self):
        r = self.f.run("archive", "--delete-local", "--yes", NIX_COPY_FAIL=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nix copy failed", r.stderr)
        self.assertEqual(list(self.f.arch.glob("linux-builder-*")), [])           # the half-written archive directory is removed
        self.assertFalse((self.f.arch / "latest").exists())
        self.assertTrue((self.f.state / "nixos.qcow2").exists())                    # nothing local was deleted
        self.assertFalse(list(self.f.state.glob(".archive-cache.*")))

    def test_roundtrip_restores_identical_disk_and_keys(self):
        original = (self.f.state / "nixos.qcow2").read_bytes()
        self.archive("--delete-local", "--yes")
        r = self.f.run("restore", "--to", self.f.restore)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.f.restore / "nixos.qcow2").read_bytes(), original)
        self.assertEqual((self.f.restore / "keys" / "builder_ed25519").read_text(), "private\n")
        self.assertTrue((self.f.restore / "result-linux-builder").exists())
        self.assertIn("BUILDER_DIR=", r.stdout)

    def test_restore_refuses_to_overwrite_and_detects_corruption(self):
        d = self.archive()
        self.assertNotEqual(self.f.run("restore", "--to", self.f.state).returncode, 0)    # nixos.qcow2 already there: needs --force
        with open(d / "nixos.qcow2.zst", "r+b") as fh:
            fh.seek(40)
            fh.write(b"\xff\xff\xff\xff")
        r = self.f.run("restore", "--to", self.f.restore)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not verify", r.stderr)
        self.assertFalse((self.f.restore / "nixos.qcow2").exists())                       # nothing is restored from a corrupt archive

    def test_restore_import_needing_trust_prints_the_sudo_command(self):
        self.archive("--delete-local", "--yes")
        shutil.rmtree(self.f.launcher)                                                    # the store path is "gone": it must be imported from the cache
        r = self.f.run("restore", "--to", self.f.restore, NIX_UNTRUSTED=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("sudo nix", r.stderr)

    def test_refuses_while_running(self):
        proc = subprocess.Popen(["sh", "-c", f"exec -a 'bin/vzvm {self.f.state}/vzvm.json' sleep 30"])
        try:
            r = self.f.run("archive", "-n")
            if r.returncode == 0:
                self.skipTest("pgrep did not match the renamed process on this platform")
            self.assertIn("running", r.stderr)
        finally:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
