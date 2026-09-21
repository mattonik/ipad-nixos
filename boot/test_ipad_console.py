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


# --- Charging tier-switcher (CHG-2, 2026-09-21) ----------------------------
import unittest.mock


class FakeSwitchShell:
    """Simulates the device's 0x04c0 register and gauge across a full
    write-then-restore cycle, so the offline test exercises the exact
    read/write/poll sequence action_charging_switch issues -- not just its
    individual commands in isolation."""

    def __init__(self, poll_responses):
        self.commands = []
        self._poll_responses = list(poll_responses)
        self._register = "0x4a"  # starts at the validated resting state

    def run(self, command, timeout=10):
        self.commands.append(command)
        touches_input_limit = "0x04 0xc0" in command
        if command.startswith("i2ctransfer") and touches_input_limit and command.endswith("r1"):
            return self._register
        if command.startswith("i2ctransfer") and touches_input_limit:
            self._register = command.rsplit(" ", 1)[-1]  # e.g. "...0x04 0xc0 0xa2"
            return ""
        if command.startswith("cat /sys/class/power_supply/bq27545-battery/uevent"):
            return self._poll_responses.pop(0)
        raise AssertionError(f"unexpected command: {command}")


def _uevent(status, current, temp_deci, capacity=50):
    return (
        f"POWER_SUPPLY_STATUS={status}\n"
        f"POWER_SUPPLY_CURRENT_NOW={current}\n"
        f"POWER_SUPPLY_VOLTAGE_NOW=3800000\n"
        f"POWER_SUPPLY_TEMP={temp_deci}\n"
        f"POWER_SUPPLY_CAPACITY={capacity}\n"
    )


def _never_touches_register_0010(commands):
    return not any("0x00 0x10" in c or "0x00 0x63" in c for c in commands)


def _writes(commands):
    return [
        c for c in commands
        if c.startswith("i2ctransfer") and "0x04 0xc0" in c and not c.endswith("r1")
    ]


# Scenario A: pick tier 2 (500 mA), six clean polls, decline to keep ->
# restores to the 1000 mA resting code (SAFE_RESTING_CODE), not Apple's
# 100 mA factory default.
shell_a = FakeSwitchShell(poll_responses=[_uevent("Discharging", "-50000", 337)] * 7)
output_a = io.StringIO()
with contextlib.redirect_stdout(output_a), \
        unittest.mock.patch("builtins.input", side_effect=["2", "n"]), \
        unittest.mock.patch("ipad_console.time.sleep", lambda *_a, **_k: None):
    ipad_console.action_charging_switch(shell_a)

assert _never_touches_register_0010(shell_a.commands), \
    "charging tier-switcher must never touch register 0x0010"
writes_a = _writes(shell_a.commands)
assert writes_a[0].endswith("0x22"), "expected the 500 mA code written first"
assert writes_a[-1].endswith(f"{ipad_console.SAFE_RESTING_CODE:#04x}"), \
    "expected a restore to the 1000 mA resting code, not the factory default"
uevent_reads = shell_a.commands.count(
    "cat /sys/class/power_supply/bq27545-battery/uevent"
)
assert uevent_reads == 7, f"expected 1 baseline + 6 poll reads, got {uevent_reads}"
print("Charging tier-switch normal-path offline safety check passed")


# Scenario B: pick tier 4 (2100 mA), TEMP crosses the 42.0C abort threshold
# on the second poll -> aborts early, restores automatically, never reaches
# the keep prompt.
shell_b = FakeSwitchShell(poll_responses=[
    _uevent("Charging", "50000", 380),   # baseline, 38.0C -- fine
    _uevent("Charging", "50000", 390),   # poll 1, 39.0C -- fine
    _uevent("Charging", "50000", 425),   # poll 2, 42.5C -- over threshold
])
output_b = io.StringIO()
with contextlib.redirect_stdout(output_b), \
        unittest.mock.patch("builtins.input", side_effect=["4"]), \
        unittest.mock.patch("ipad_console.time.sleep", lambda *_a, **_k: None):
    ipad_console.action_charging_switch(shell_b)

assert _never_touches_register_0010(shell_b.commands)
writes_b = _writes(shell_b.commands)
assert writes_b[0].endswith("0xa2"), "expected the 2100 mA code written first"
assert writes_b[-1].endswith(f"{ipad_console.SAFE_RESTING_CODE:#04x}"), \
    "expected an automatic restore to 1000 mA on thermal abort"
uevent_reads_b = shell_b.commands.count(
    "cat /sys/class/power_supply/bq27545-battery/uevent"
)
assert uevent_reads_b == 3, f"expected 1 baseline + 2 poll reads before abort, got {uevent_reads_b}"
assert "abort" in output_b.getvalue().lower()
print("Charging tier-switch thermal-abort offline safety check passed")
