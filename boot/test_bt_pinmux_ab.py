#!/usr/bin/env python3
"""Contract test for boot/bt_pinmux_ab.py: only approved writes plus PERIPH on GPIO 14/32, restore in finally, only the HCI Reset (via bt_3m_probe.probe) is sent."""
from pathlib import Path
import re

src = Path(__file__).with_name("bt_pinmux_ab.py").read_text()
writes = re.findall(r"i2ctransfer -f -y 0 w3@0x3c (0x[0-9a-f]{2}) (0x[0-9a-f]{2}) (0x[0-9a-f]{2})", src)
assert sorted(set(writes)) == [("0x04", "0x02", "0x09"), ("0x04", "0x02", "0x0b")], writes
assert set(re.findall(r"pinpoke (high|low|restore) (\d+)", src)) <= {("high", "164"), ("restore", "164")}
assert "FUNC_PINS = (14, 32)" in src and "pinpoke func {p}" in src
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE")
restore = src[src.index("--- RESTORE"):]
for needle in ("w3@0x3c 0x04 0x02 0x09", "pinpoke restore 164", "pinpoke func {p} {periph(orig[p])}", "uartpoke set {o28}"):
    assert needle in restore, needle
assert src.index("periph(v) != 2") < src.index("try:"), "baseline must be function 2 before any write"
assert "printf" not in src, "UART traffic only through bt_3m_probe.probe (the 4-byte HCI Reset)"
for forbidden in ("i2cset", "wpa_", "devmem", "0x0010 0x", "0x04c0 0x"):
    assert forbidden not in src, forbidden
print("PASS")
