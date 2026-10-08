#!/usr/bin/env python3
"""Offline test for boot/h1b_query.py (fake shell; no device)."""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1b_query as Q


class FakeShell:
    def __init__(self):
        self.commands = []

    def run(self, command, timeout=10, check=True):
        self.commands.append(command)
        return "shared 00000000: 00000005\n" if "query" in command else ""


def main():
    for bad in ("tcm 0x0", "core arm 0 4", 'tcm 0 4; reboot', "write 0x0 1", "tcm 0x0 4 > /x", "core pcie2 0x0 4\nrm", "shared extra", ""):
        try:
            Q.validate(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    for good in ("tcm 0x1000 256", "tcm 4096 64", "core pcie2 0x0 256", "core cc 0x58 32", "shared", "rings", "console"):
        assert Q.validate(good) == good
    with tempfile.TemporaryDirectory() as tmp:
        shell = FakeShell()
        out, results = Q.run_queries(shell, tmp, list(Q.DEFAULT), now="T")
        assert out.name == "queries-T" and oct(out.stat().st_mode & 0o777) == "0o700"
        assert len(results) == len(Q.DEFAULT) and len(list(out.iterdir())) == len(Q.DEFAULT)
        for f in out.iterdir():
            assert oct(f.stat().st_mode & 0o777) == "0o600"
        # The only device-side effects: mount debugfs, write the validated query text, cat the result.
        assert shell.commands[0].startswith("mountpoint -q /sys/kernel/debug")
        for c in shell.commands[1:]:
            assert c.startswith('echo "') and c.endswith("/query && cat " + Q.DIR + "/result"), c
        try:
            Q.run_queries(shell, tmp, ["shared; reboot"], now="U")
        except ValueError:
            assert not (Path(tmp) / "queries-U").exists()
        else:
            raise AssertionError("injection accepted")
    for rom in ("unlock rom", "rom 0x0 256"):
        try:
            Q.validate(rom)
        except ValueError as e:
            assert "--allow-rom" in str(e)
        else:
            raise AssertionError("rom accepted without --allow-rom")
        assert Q.validate(rom, allow_rom=True) == rom
    for bad in ("rom 0x0", "unlock", "unlock rom now", "snap 1", "diff all"):
        try:
            Q.validate(bad, allow_rom=True)
        except ValueError:
            continue
        raise AssertionError(bad)
    for good in ("snap", "diff", "arm"):
        assert Q.validate(good) == good
    print("PASS")


if __name__ == "__main__":
    main()
