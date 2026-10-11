#!/usr/bin/env python3
"""Contract test for boot/uartpoke.c and boot/uart3_baud_experiment.py: UART3 baud registers only, restore in finally, no PMIC/GPIO writes."""
from pathlib import Path
import re

c = Path(__file__).with_name("uartpoke.c").read_text()
assert "#define UART3_BASE 0x20a0cc000ULL" in c
assert len(re.findall(r"r\[REG_BAUD\d / 4\] = ", c)) == 3, "exactly the three baud registers are written"
assert len(re.findall(r"r\[REG_UFCON / 4\] = ", c)) == 1 and "v & ~0x1ffu" in c, "UFCON (+0x08) written once, limited to 9 bits"
assert len(re.findall(r"r\[REG_UCON / 4\] = ", c)) == 1 and "(v & 0x3a10u)" in c and "(v & 0x85u) != 0x85u" in c, "UCON written once; break and interrupt-enable bits refused"
assert "REG_BAUD0 0x28" in c and "REG_BAUD1 0x34" in c and "REG_BAUD2 0x38" in c
p = Path(__file__).with_name("uart3_baud_experiment.py").read_text()
assert "finally:" in p and p.index("finally:") < p.index("--- RESTORE")
for forbidden in ("i2ctransfer", "pinpoke", "devmem", "wpa_", "0x0402"):
    assert forbidden not in p, forbidden
print("PASS")
