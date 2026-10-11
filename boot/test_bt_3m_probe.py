#!/usr/bin/env python3
"""Contract test for boot/bt_3m_probe.py: writes limited to the approved registers, restore in finally, only the 4-byte HCI Reset is sent."""
from pathlib import Path
import re

src = Path(__file__).with_name("bt_3m_probe.py").read_text()
writes = re.findall(r"i2ctransfer -f -y 0 w3@0x3c (0x[0-9a-f]{2}) (0x[0-9a-f]{2}) (0x[0-9a-f]{2})", src)
assert sorted(set(writes)) == [("0x04", "0x02", "0x09"), ("0x04", "0x02", "0x0b")], writes
assert all(p == "164" for _, p in re.findall(r"pinpoke (high|low|restore) (\d+)", src)) and re.findall(r"pinpoke (high|low|restore)", src)
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE")
assert src.count("printf '\\\\001\\\\003\\\\014\\\\000'") == 1, "exactly the 4-byte HCI Reset is sent"
for forbidden in ("i2cset", "wpa_", "devmem", "0x0010 0x", "0x04c0 0x"):
    assert forbidden not in src, forbidden
print("PASS")
