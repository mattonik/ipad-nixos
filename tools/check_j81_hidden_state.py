#!/usr/bin/env python3
"""Check the exact J81 GPU dependency, DWI stores, and historical Linux rail samples."""
import argparse
from pathlib import Path
import re
import struct

from audit_j81_pmgr_start import checked_file, property_at


def check(kernel_path, tree_path, capture):
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    tree = checked_file(tree_path, "be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003")
    records = dict((r[3], r) for r, in struct.iter_unpack("48s", property_at(tree, 0x74f8, b"devices")))
    banks = list(struct.iter_unpack("<III", property_at(tree, 0x6a1c, b"ps-regs")))
    for ident, name, addr, parents in [(124, "GFX", 0x20320, []), (54, "DWI", 0x20120, []),
                                       (70, "I2C0", 0x20160, [4]), (4, "SIO_P", 0x201f8, [])]:
        row = records[ident]
        region, base, _ = banks[row[11]]
        if (row[32:].rstrip(b"\0").decode(), region, base + 8*row[10],
                list(row[4:8].rstrip(b"\0"))) != (name, 0, addr, parents):
            raise ValueError(f"unexpected power-state record for {name}")
    if len(records) != 98 or any(124 in row[4:8] for row in records.values()):
        raise ValueError("unexpected GFX dependent")
    print("PASS: GFX has zero PMGR parents and zero reverse edges across 98 devices")
    # Decode the STR Wt,[X9,#imm12*4] addressing mode in the DWI startup path.
    offsets = []
    for pos in (0x21464d4, 0x21464dc, 0x21464e4, 0x21464e8, 0x21464f0):
        word, = struct.unpack_from("<I", kernel, pos)
        if word & 0xffc003e0 != 0xb9000120:
            raise ValueError(f"unexpected DWI store at {pos:#x}")
        offsets.append(4 * ((word >> 10) & 4095))
    if offsets != [0, 0x50, 4, 0x14, 0x10]:
        raise ValueError("unexpected pre-banner DWI store sequence")
    print("PASS: five DWI store offsets before its startup message:", [hex(x) for x in offsets])
    phases = [("before-dwi", 0x200, 0, 0, 0x40), ("before-gpc", 0xff, 0, 0, 0x40),
              ("after-gpc", 0xff, 0x164, 0x64, 0x64), ("after-10s", 0xff, 0x164, 0x64, 0x64)]
    for phase, dwi, vid, b0, b2 in phases:
        log = (capture / f"{phase}-pmgr.log").read_text()
        words = {int(a,16): int(v,16) for a,v in re.findall(r"^w (0x\w+) raw=(0x\w+)$", log, re.M)}
        row = [int(x,16) for x in (capture / f"{phase}-pmu-0128.log").read_text().split()]
        if len(row) != 8 or (words[0x20120], words[0x2300c], words[0x5004], row[0], row[2]) != (dwi, vid, 0, b0, b2):
            raise ValueError(f"historical capture mismatch during {phase}")
        print(f"{phase}: DWI={dwi:#x} GFX_VID={vid:#x} PMU[128,12a]={b0:02x}/{b2:02x} page5=0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("kernel", "tree", "capture"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    check(args.kernel, args.tree, args.capture)
