#!/usr/bin/env python3
"""Contract test for boot/bt_chip_gpio_watch.py: only the safe ChipCommon read, only the approved writes, restore in finally."""
from pathlib import Path
import importlib.util
import re

p = Path(__file__).with_name("bt_chip_gpio_watch.py")
src = p.read_text()
assert src.count('"core cc 0x58 24"') == 1 and not re.search(r'core (pcie2|cc) 0x(?!58 24)', src), "only the safe ChipCommon GPIO block is read"
writes = re.findall(r"i2ctransfer -f -y 0 w3@0x3c (0x[0-9a-f]{2}) (0x[0-9a-f]{2}) (0x[0-9a-f]{2})", src)
assert sorted(set(writes)) == [("0x04", "0x02", "0x09"), ("0x04", "0x02", "0x0b")], writes
assert all(x == "164" for _, x in re.findall(r"pinpoke (high|low|restore) (\d+)", src))
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE")
for forbidden in ("tcm 0x", "rom 0x", "unlock rom", "uartpoke", "devmem"):
    assert forbidden not in src, forbidden
spec = importlib.util.spec_from_file_location("w", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.diff([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]) == ["no change"]
assert "gpioin: 00000003 -> 00000007" in m.diff([0, 0, 3, 0, 0, 0], [0, 0, 7, 0, 0, 0])[0]
print("PASS")
