#!/usr/bin/env python3
"""Exercise the PongoOS ADT capture without hardware."""

import contextlib
import io
import runpy
import sys
import tempfile
import types
from pathlib import Path


sample = b"""target-type                      J81
platform-name                    74 37 30 30 31 00 |t7001.|
regulatory-model-number          41 31 35 36 36 00 |A1566.|
name                             device-tree
    name                         uart3
        name                     bluetooth
    name                         uart5
        name                     gas-gauge
"""
transfers = []


class Device:
    def __init__(self):
        self.issued = False
        self.stale = [b"old output", b""]
        self.chunks = [sample[:80], sample[80:190], sample[190:]]

    def set_configuration(self):
        pass

    def ctrl_transfer(self, *args, **kwargs):
        transfers.append((args, kwargs))
        if args[:2] == (0x21, 3):
            self.issued = True
            return len(args[4])
        if args[:2] == (0xA1, 1):
            source = self.chunks if self.issued else self.stale
            return source.pop(0) if source else b""
        raise AssertionError(args)


usb = types.ModuleType("usb")
core = types.ModuleType("usb.core")
core.USBError = RuntimeError
core.find = lambda **_kwargs: Device()
usb.core = core
sys.modules["usb"] = usb
sys.modules["usb.core"] = core

with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "j81.adt"
    old_argv = sys.argv
    sys.argv = [
        "dump_adt.py",
        "--output",
        str(output),
        "--wait-seconds",
        "0",
        "--timeout",
        "1",
        "--idle-seconds",
        "0.01",
        "--min-bytes",
        "1",
    ]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(Path(__file__).with_name("dump_adt.py"), run_name="__main__")
    finally:
        sys.argv = old_argv

    assert output.read_bytes() == sample
    assert output.stat().st_mode & 0o777 == 0o600

assert any(call[0][:5] == (0x21, 3, 0, 0, b"dt\n") for call in transfers)
print("ADT capture test passed")
