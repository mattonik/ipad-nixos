#!/usr/bin/env python3
"""Exercise --diagnostic without a USB device; it must never send bootl."""
import builtins
import io
import runpy
import sys
import types
from pathlib import Path

commands = []
diagnostic_reads = 0


class Device:
    def set_configuration(self):
        pass

    def ctrl_transfer(self, request_type, request, value, index, data=0, **_kwargs):
        global diagnostic_reads
        if request == 3:
            commands.append(data)
        if request_type == 0xa1 and request == 1:
            diagnostic_reads += 1
            if diagnostic_reads == 1:
                return b"Found device tree for J81 (26581 bytes).\n"
            return b"[t7001] candidate-entry=0x800080000; diagnostic only, no jump attempted.\n\0"
        return b""

    def write(self, _endpoint, _data, _timeout=None):
        return None


usb = types.ModuleType("usb")
core = types.ModuleType("usb.core")
core.USBError = RuntimeError
core.find = lambda **_kwargs: Device()
usb.core = core
sys.modules["usb"] = usb
sys.modules["usb.core"] = core

old_argv, old_open = sys.argv, builtins.open
sys.argv = ["load_linux.py", "--diagnostic", "-k", "kernel", "-d", "dtb"]
builtins.open = lambda _path, _mode: io.BytesIO(b"payload")
try:
    runpy.run_path(Path(__file__).with_name("load_linux.py"), run_name="__main__")
finally:
    sys.argv, builtins.open = old_argv, old_open

assert b"linux_diag\n" in commands
assert b"bootl\n" not in commands
print("diagnostic uploader test passed")
