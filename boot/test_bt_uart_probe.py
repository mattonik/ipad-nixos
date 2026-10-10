#!/usr/bin/env python3
"""Contract test for boot/bt_uart_probe.py: the probe may send only the standard HCI Reset and must never write a PMIC/GPIO register or touch Wi-Fi."""
from pathlib import Path
import re

text = (Path(__file__).with_name("bt_uart_probe.py")).read_text()
assert r"\001\003\014\000" in text, "the probe must send the 4-byte HCI Reset"
for forbidden in ("i2ctransfer", "i2cset", "wpa_", "iw dev", "/sys/class/gpio", "devmem", "/dev/mem", "gpioset"):
    assert forbidden not in text, forbidden
assert len(re.findall(r"printf '", text)) == 1, "exactly one raw write to the UART"
assert "btattach" in text and "sys.exit" in text, "must refuse to run while an HCI device or btattach is active"
print("PASS")
