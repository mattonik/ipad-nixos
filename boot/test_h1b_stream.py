#!/usr/bin/env python3
"""Offline test for boot/h1b_stream.py (fake shell; no device)."""
from pathlib import Path
import stat
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1b_stream as S


class FakeShell:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.commands = []

    def run(self, command, timeout=10, check=True):
        self.commands.append(command)
        if not self.outputs:
            raise OSError(49, "Can't assign requested address")
        return self.outputs.pop(0)


def main():
    assert S.new_lines("a\nb\n", "a\nb\nc\n") == "c\n"
    assert S.new_lines("a\nb\n", "a\nb\n") == ""
    assert S.new_lines("a\nb\n", "x\ny\n") == "x\ny\n"
    with tempfile.TemporaryDirectory() as tmp:
        shell = FakeShell(["[0] boot\n", "[0] boot\n[1] pcie\n", "[0] boot\n[1] pcie\n[2] fw\n"])
        out = Path(tmp) / "s.log"
        S.stream(shell, out, deadline_s=60, sleep=lambda s: None)
        text = out.read_text()
        assert text.startswith("[0] boot\n[1] pcie\n[2] fw\n") and "# link lost: OSError" in text
        assert stat.S_IMODE(out.stat().st_mode) == 0o600
        assert set(shell.commands) == {"dmesg"}, shell.commands  # read-only: nothing else is ever sent
    print("PASS")


if __name__ == "__main__":
    main()
