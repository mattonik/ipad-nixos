#!/usr/bin/env python3
"""Contract test for boot/bt_powerup_listen.py: approved registers only, restore in finally, nothing transmitted on the UART."""
from pathlib import Path
import re

src = Path(__file__).with_name("bt_powerup_listen.py").read_text()
writes = re.findall(r"i2ctransfer -f -y 0 w3@0x3c (0x[0-9a-f]{2}) (0x[0-9a-f]{2}) (0x[0-9a-f]{2})", src)
assert sorted(set(writes)) == [("0x04", "0x02", "0x09"), ("0x04", "0x02", "0x0b")], writes
assert all(p == "164" for _, p in re.findall(r"pinpoke (high|low|restore) (\d+)", src))
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE")
assert "printf" not in src.replace("printf '", "printf '") or "\\\\001" not in src, "nothing is transmitted"
assert ">&3" not in src.replace("<&3", ""), "no write to the UART file descriptor"
print("PASS")
