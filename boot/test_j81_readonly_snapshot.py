#!/usr/bin/env python3
"""Host-only contract check for the J81 read-only snapshot."""
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import j81_readonly_snapshot as R  # noqa: E402


class FakeShell:
    def __init__(self):
        self.commands = []

    def run(self, command, **kwargs):
        self.commands.append(command)
        return "kernel [1] test MAC 00:11:22:33:44:55 UUID e9d7c9ed-8d71-49c3-a271-31a9dd8a74ac"


with tempfile.TemporaryDirectory() as tmp:
    shell = FakeShell()
    out = R.capture(shell, tmp, now="test")
    assert [p.stem for p in sorted(out.glob("*.txt"))] == sorted(name for name, _ in R.COMMANDS)
    assert shell.commands == [command for _, command in R.COMMANDS]
    assert all("[MAC]" in p.read_text() and "[UUID]" in p.read_text() for p in out.glob("*.txt"))
    assert oct(os.stat(out).st_mode & 0o777) == "0o700"
    assert all(oct(os.stat(p).st_mode & 0o777) == "0o600" for p in out.glob("*.txt"))
    assert all(not any(token in c for token in ("insmod", "modprobe", "echo 1", " > ", "tee ", "dd ", "reboot", "poweroff"))
               for c in shell.commands)
    ranges = dict(R.COMMANDS)["fdt_memory_ranges"]
    assert "od -An -v -tx1" in ranges and "linux,usable-memory-range" in ranges
    assert "reserved-memory/*" in ranges and "-maxdepth" not in " ".join(c for _, c in R.COMMANDS)
    identity = dict(R.COMMANDS)["boot_identity"]
    assert "/proc/sys/kernel/random/boot_id" in identity and "sha256sum /sys/kernel/notes" in identity
print("PASS: one-session snapshot command set, private files, and identifier redaction")
