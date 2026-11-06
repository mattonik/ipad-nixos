#!/usr/bin/env python3
"""Static safety contract for the read-only Fender status module."""
from pathlib import Path

source = (Path(__file__).parent / "gpu-fender-status/gpu-fender-status.c").read_text()
assert "FENDER_BASE 0x201e00000ULL" in source
assert "FENDER_SIZE 0x21000" in source
assert "readl(fender + STATE_OFF)" in source
assert "readl(fender + CONTROL_OFF)" in source
assert "readl(fender + HOLD_OFF)" in source
assert "writel(" not in source and "writeq(" not in source
assert "201000000" not in source, "status module must not touch RGX"
assert "device_create_file(status_device, &dev_attr_state)" in source
print("PASS: Fender status module is read-only, bounded and RGX-free")
