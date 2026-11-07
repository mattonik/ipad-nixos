#!/usr/bin/env python3
"""Contract test for boot/uartpeek.c: read-only, two allow-listed UART bases, no writes."""
from pathlib import Path
import re

src = Path(__file__).with_name("uartpeek.c").read_text()
assert "O_RDONLY" in src and "O_RDWR" not in src and "PROT_READ," in src and "PROT_WRITE" not in src
assert re.findall(r"base = (0x[0-9a-f]+)ULL", src) == ["0x20a0cc000", "0x20a0d4000"]
assert re.findall(r"MAP_SHARED, fd, (0x[0-9a-f]+)ULL", src) == ["0x20e020000"], "the PMGR window is the only other mapping"
assert "for (i = 0x50; i <= 0x59; i++)" in src, "PMGR reads limited to PS indices 0x50..0x59"
assert 'printf("PS index 0x%02x @0x20e02%04x:' in src
assert "UART%d" not in src, "PMGR state indices are not UART device IDs"
assert not re.search(r"\br\[[^\]]*\]\s*=[^=]", src), "no register stores"
assert "only UART 3 and 5 are allowed" in src
print("PASS")
