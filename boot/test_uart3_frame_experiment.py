#!/usr/bin/env python3
"""Contract test for boot/uart3_frame_experiment.py: UART3 only via uartpoke, restore in finally, and the linear fit recovers slope/intercept."""
from pathlib import Path
import importlib.util

p = Path(__file__).with_name("uart3_frame_experiment.py")
src = p.read_text()
assert "finally:" in src and src.index("finally:") < src.index("--- RESTORE")
for forbidden in ("i2ctransfer", "pinpoke", "devmem", "wpa_", "0x0402"):
    assert forbidden not in src, forbidden
spec = importlib.util.spec_from_file_location("fe", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# 100 kbaud with 4 bits of overhead: time/byte = (n + 4) / 100000
pts = [(n, (n + 4) / 100000) for n in (7, 8, 9, 10, 11, 12)]
slope, icpt = m.fit(pts)
assert abs(1 / slope - 100000) < 1 and abs(icpt / slope - 4) < 1e-6
print("PASS")
