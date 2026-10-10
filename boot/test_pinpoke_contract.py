#!/usr/bin/env python3
"""Contract test for boot/pinpoke.c: it may write only the allow-listed BT_WAKE pin and must refuse lock/peripheral-changing restores."""
from pathlib import Path
import re

src = Path(__file__).with_name("pinpoke.c").read_text()
assert "#define WRITE_PIN 164" in src
assert "#define PINCTRL_BASE 0x20e300000ULL" in src
assert src.count("*reg = ") == 2, "exactly two write sites (high/low and restore)"
assert "if (pin != WRITE_PIN)" in src and src.index("if (pin != WRITE_PIN)") < src.index("*reg = v;"), "the pin check must precede every write"
for needle in ("REG_LOCK", "REG_PERIPH_MASK", "refusing a value that sets the lock bit"):
    assert needle in src
assert not re.search(r'system\s*\(|exec[lv]p?\s*\(|fork\s*\(', src)
print("PASS")
