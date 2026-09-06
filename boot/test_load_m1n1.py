#!/usr/bin/env python3
"""Exercise the m1n1 uploader without hardware."""

import builtins
import io
import runpy
import struct
import sys
import types
from pathlib import Path

payload = b"m1n1-test-payload"
transfers = []
uploads = []


class Device:
    def set_configuration(self):
        pass

    def ctrl_transfer(self, *args, **kwargs):
        transfers.append((args, kwargs))
        return b""

    def write(self, endpoint, data, timeout=None):
        uploads.append((endpoint, data, timeout))
        return len(data)


usb = types.ModuleType("usb")
core = types.ModuleType("usb.core")
core.USBError = RuntimeError
core.find = lambda **_kwargs: Device()
usb.core = core
sys.modules["usb"] = usb
sys.modules["usb.core"] = core

old_argv, old_open = sys.argv, builtins.open
sys.argv = ["load_m1n1.py", "payload"]
builtins.open = lambda _path, _mode: io.BytesIO(payload)
try:
    runpy.run_path(Path(__file__).with_name("load_m1n1.py"), run_name="__main__")
finally:
    sys.argv, builtins.open = old_argv, old_open

assert uploads == [(2, payload, 1_000_000)]
# Discard any previously buffered upload before starting a new one --
# matches load_linux.py's own sequence (bRequest 2, wLength 0).
assert transfers[0][0][0:4] == (0x21, 2, 0, 0)
assert transfers[1][0][0:4] == (0x21, 1, 0, 0)
assert transfers[1][0][4] == struct.pack("<I", len(payload))
assert any(call[0][0:5] == (0x21, 3, 0, 0, b"bootm\n") for call in transfers)
print("m1n1 uploader test passed")
