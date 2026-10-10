#!/usr/bin/env python3
"""Contract test for boot/bt_wake_experiment.py: writes are limited to the two approved registers and the restore is in a finally block."""
from pathlib import Path
import re

src = Path(__file__).with_name("bt_wake_experiment.py").read_text()
writes = re.findall(r"i2ctransfer -f -y 0 w3@0x3c (0x[0-9a-f]{2}) (0x[0-9a-f]{2}) (0x[0-9a-f]{2})", src)
assert sorted(set(writes)) == [("0x04", "0x02", "0x09"), ("0x04", "0x02", "0x0b")], writes
assert re.findall(r"pinpoke (high|low|restore) (\d+)", src) and all(p == "164" for _, p in re.findall(r"pinpoke (high|low|restore) (\d+)", src))
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE") < src.index("gpio2_restore_rc"), "restore must run in a finally block"
assert "sys.exit(\"unexpected baseline" in src, "must refuse to write when the baseline differs"
for forbidden in ("i2cset", "wpa_", "iw dev", "devmem", "/sys/class/gpio", "0x04c0 0x", "0x0010 0x"):
    assert forbidden not in src, forbidden
print("PASS")
