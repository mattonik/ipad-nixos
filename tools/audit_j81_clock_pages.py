#!/usr/bin/env python3
"""Compare the J81 Linux clock-page sample with the captured arm-io rate table."""
import argparse
from pathlib import Path
import re
import struct

from audit_gpu_bridge_plan import capture_table


def llb_rate(control, status, config):
    # J81 19H422 LLB 0x18039098c..0x1803909d0. ARM64 UDIV by zero returns zero.
    if not control & (1 << 31):
        return 24_000_000 if status & 1 else 0
    predivider = (control >> 4) & 31
    multiplier = (control >> 12) & 511
    if config & (1 << 27):
        numerator = 48_000_000 * multiplier
    else:
        numerator = 24_000_000 * multiplier // (1 + (control & 15))
    return (numerator // predivider) & 0xffffffff if predivider else 0


def compare(sample, adt):
    lines = sample.splitlines()
    start = "stage=before-pmgr-words-read base=0x20e000000 words=42"
    end = "stage=after-pmgr-words-read"
    if lines.count(start) != 1 or lines.count(end) != 1:
        raise ValueError("expected one complete 42-word register sample")
    words = {}
    for line in lines[lines.index(start) + 1:lines.index(end)]:
        row = re.fullmatch(r"w 0x([0-9a-fA-F]+) raw=0x([0-9a-fA-F]{8})", line)
        if row:
            offset, value = (int(field, 16) for field in row.groups())
            if offset in words:
                raise ValueError(f"duplicate offset {offset:#x}")
            words[offset] = value
    expected = {page * 4096 + offset for page in range(6) for offset in range(0, 28, 4)}
    if set(words) != expected:
        raise ValueError("incomplete or unexpected register coverage")
    table = capture_table(adt, "clock-frequencies")
    if len(table) != 384:
        raise ValueError("expected the captured J81 96-entry clock table")
    slots = struct.unpack("<96I", table)
    print("page  Linux +8    modeled +8  old calc Hz  new calc Hz  ADT slot Hz")
    for page in range(6):
        base = page * 4096
        config = words[base + 8]
        requested = (config & 0x3fffffff) | 0x40000000 if page in (1, 4) else config
        before = llb_rate(words[base], words[base + 4], config)
        after = llb_rate(words[base], words[base + 4], requested)
        print(f"{page:4}  {config:08x}    {requested:08x}    {before:10}  {after:10}  {slots[page + 1]:11}")
        if before != after:
            raise ValueError("changing +8[31:30] affected the modeled rate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path, help="completed Linux plls.log")
    parser.add_argument("adt", type=Path, help="captured J81 ADT text with populated clock-frequencies")
    args = parser.parse_args()
    try:
        compare(args.sample.read_text(), args.adt.read_text())
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
