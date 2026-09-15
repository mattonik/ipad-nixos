#!/usr/bin/env python3
"""Offline safety check for the D2207 charging snapshot."""
import contextlib
import io
import sys

sys.path.insert(0, "boot")
import ipad_console


class FakeShell:
    values = {
        f"cat {ipad_console.CHARGER}/input_current_limit": "3262000",
        f"cat {ipad_console.CHARGER}/constant_charge_current_max": "3000000",
        "i2ctransfer -f -y 0 w2@0x3c 0x04 0xc0 r1": "0xfe",
        "i2ctransfer -f -y 0 w2@0x3c 0x04 0xcf r1": "0x3c",
    }

    def __init__(self):
        self.commands = []

    def run(self, command, timeout=10):
        assert timeout == 10
        self.commands.append(command)
        return self.values[command]


shell = FakeShell()
output = io.StringIO()
with contextlib.redirect_stdout(output):
    ipad_console.action_charging_observe(shell)

assert shell.commands == list(FakeShell.values)
assert all(command.startswith(("cat ", "i2ctransfer ")) for command in shell.commands)
assert all(" r1" in command for command in shell.commands if command.startswith("i2ctransfer "))
assert output.getvalue().count("compare: MATCH") == 2
print("D2207 charging snapshot offline safety check passed")
