#!/usr/bin/env python3
"""Offline checks for the bounded Bluetooth probe."""
import sys

sys.path.insert(0, "boot")
import bt_probe


class FakeShell:
    def run(self, command, timeout=10):
        assert timeout == 10
        if "bluetooth" in command:
            return "address AA:BB:CC:DD:EE:FF\n"
        return "ok\n"


for name, command in bt_probe.COMMANDS:
    lowered = command.lower()
    assert "i2cset" not in lowered, name
    assert "reboot" not in lowered and "poweroff" not in lowered, name
    assert "modprobe" not in lowered and "insmod" not in lowered, name
    assert "nohup btattach" not in lowered, name

report = bt_probe.collect_snapshot(FakeShell())
assert "<redacted-mac>" in report
assert "===== pmic-gpio2 =====" in report
assert "AA:BB:CC:DD:EE:FF" not in report
print("Bluetooth probe offline safety check passed")
