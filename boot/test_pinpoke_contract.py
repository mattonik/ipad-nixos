#!/usr/bin/env python3
"""Contract test for boot/pinpoke.c: full writes only on the BT_WAKE pin; on UART3 TX/RTS (14, 32) only the PERIPH field, to 1 or 2; locks refused."""
from pathlib import Path
import re

src = Path(__file__).with_name("pinpoke.c").read_text()
assert "#define WRITE_PIN 164" in src
assert "#define PINCTRL_BASE 0x20e300000ULL" in src
assert src.count("*reg = ") == 3, "exactly three write sites (func, high/low, restore)"
assert "#define FUNC_PIN_TX 14" in src and "#define FUNC_PIN_RTS 32" in src
func = src[src.index('strcmp(argv[1], "func")'):src.index("if (pin != WRITE_PIN)")]
assert func.index("pin != FUNC_PIN_TX && pin != FUNC_PIN_RTS") < func.index("*reg = v;"), "func pin check precedes its write"
assert "REG_LOCK" in func and func.index("REG_LOCK") < func.index("*reg = v;")
assert "v = (v & ~REG_PERIPH_MASK) | ((uint32_t)f << 5);" in func, "func changes PERIPH only"
assert 'strcmp(argv[3], "1") != 0 && strcmp(argv[3], "2") != 0' in func, "only functions 1 and 2"
rest = src[src.index("if (pin != WRITE_PIN)"):]
assert rest.count("*reg = ") == 2, "the high/low/restore writes stay behind the WRITE_PIN check"
for needle in ("REG_LOCK", "REG_PERIPH_MASK", "refusing a value that sets the lock bit"):
    assert needle in src
assert not re.search(r'system\s*\(|exec[lv]p?\s*\(|fork\s*\(', src)
print("PASS")
