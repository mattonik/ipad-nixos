#!/usr/bin/env python3
"""Find ADR instructions in a flat PRELINK_TEXT.raw that point at given addresses.

Usage: find_adr_refs.py RAW BASE_ADDR TARGET [TARGET...]   (hex addresses)

Ghidra run with -noanalysis misses string references made with ADR (as these 2014 kexts do) and
code only reached through vtables. This scans every 4-byte word, so it also finds references
from code Ghidra never made a function of; feed the hits to MakeFuncDecomp.java.
"""
import struct
import sys

raw = open(sys.argv[1], "rb").read()
base = int(sys.argv[2], 16)
targets = {int(t, 16): [] for t in sys.argv[3:]}
for off in range(0, len(raw) - 3, 4):
    w = struct.unpack_from("<I", raw, off)[0]
    if (w & 0x9F000000) == 0x10000000:
        imm = ((w >> 5) & 0x7FFFF) << 2 | ((w >> 29) & 3)
        if imm & (1 << 20):
            imm -= 1 << 21
        t = base + off + imm
        if t in targets:
            targets[t].append(hex(base + off))
for t, hits in targets.items():
    print(hex(t), hits)
