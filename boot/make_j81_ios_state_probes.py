#!/usr/bin/env python3
"""Build the iPadOS state probes for J81 by patching instruction words of the run-3 KPF module.

Base: run-3 module (pmgr-bisect v3, sha256 0a20ead8...): hook at the end of ApplePMGR::start(), the
unmodified Linux-style GFX/bridge/GPC sequence, P0 and P1 records through the AGXk logger, and a
core-ID read mapped with ml_io_map. Every variant changes only the address of reads that are
print-only (no control flow depends on them) and never adds a store:
  page14  P0 F/P -> PMGR +0x1008 / +0x4008 (before GPC); P1 F1/F2 -> +0x1008 / +0x4008 (after GPC,
          after page 5; F3 stays page 5 +4, which still gates the core read)
  fender  P1 G= becomes a real read of Fender +0 (physical 0x201e00000) through the ORIGINAL ml_io_map
          pointer: the pointer (x23 right after the map call) is saved to a free stack slot and the
          G read, which used x23 after it had been re-pointed at the log buffer, loads it back
  cpuNN   the core-ID mapping (0x201000000) becomes the CPU cluster resource 0x202220000 and the
          one read there becomes +0xNN; the printed CORE= value is that word (core ID not read)
"""
import hashlib
import struct
import sys
from pathlib import Path

BASE_SHA = "0a20ead86eadb28d5743136f5e8e2b163abcb37369b873046595e3f26b84c213"
ADD_X0_X20_1 = 0x91400680   # add x0, x20, #1, lsl #12
ADD_X0_X20_4 = 0x91401280   # add x0, x20, #4, lsl #12
ADD_X0_X0_8 = 0x91002000    # add x0, x0, #8
OLD_PAGE5_A, OLD_PAGE5_B = 0x91401680, 0x91001000           # add x0,x20,#5,lsl#12 ; add x0,x0,#4
OLD_PERF_A, OLD_PERF_B = 0x91407280, 0x91080000             # add x0,x20,#0x1c,lsl#12 ; add x0,x0,#0x200
OLD_MOVZ, NEW_MOVZ = 0xd2a02000, 0xd2a04440                 # movz x0,#0x100,lsl#16 -> #0x222,lsl#16 (+ movk #2,lsl#32 kept)
OLD_CORE_ADD = 0x91008300                                   # add x0, x24, #0x20
STR_X23_SP440, LDR_X0_SP440 = 0xf90223f7, 0xf94223e0        # str x23,[sp,#0x440] ; ldr x0,[sp,#0x440]
OLD_MOV_W25_W0, OLD_CBZ_W25, NEW_CBZ_W0 = 0x2a0003f9, 0x34000079, 0x34000060
OLD_MOV_X0_X23 = 0xaa1703e0
CPU_OFFSETS = (0x20, 0x48, 0x150, 0x190, 0x194, 0x1a0, 0x1b0)


def add_x0_x24(imm: int) -> int:
    assert 0 < imm < 0x1000
    return 0x91000300 | (imm << 10)


def patches(name: str) -> list[tuple[int, int, int]]:
    """(file offset, expected old word, new word)."""
    if name == "page14":
        return [(0x413c, OLD_PAGE5_A, ADD_X0_X20_1), (0x4140, OLD_PAGE5_B, ADD_X0_X0_8),
                (0x414c, OLD_PERF_A, ADD_X0_X20_4), (0x4150, OLD_PERF_B, ADD_X0_X0_8),
                (0x4394, OLD_PAGE5_A, ADD_X0_X20_1), (0x4398, OLD_PAGE5_B, ADD_X0_X0_8),
                (0x43a4, OLD_PAGE5_A, ADD_X0_X20_4), (0x43a8, OLD_PAGE5_B, ADD_X0_X0_8)]
    if name == "fender":
        return [(0x42e8, OLD_MOV_W25_W0, STR_X23_SP440), (0x42ec, OLD_CBZ_W25, NEW_CBZ_W0),
                (0x43f0, OLD_MOV_X0_X23, LDR_X0_SP440)]
    if name.startswith("cpu"):
        offset = int(name[3:], 16)
        assert offset in CPU_OFFSETS
        return [(0x4490, OLD_MOVZ, NEW_MOVZ), (0x44cc, OLD_CORE_ADD, add_x0_x24(offset))]
    raise ValueError(name)


def names() -> list[str]:
    return ["page14", "fender"] + [f"cpu{offset:x}" for offset in CPU_OFFSETS]


def build(base: bytes, name: str) -> bytes:
    if hashlib.sha256(base).hexdigest() != BASE_SHA:
        raise ValueError("base module checksum mismatch")
    data = bytearray(base)
    for offset, old, new in patches(name):
        if struct.unpack_from("<I", data, offset)[0] != old:
            raise ValueError(f"unexpected word at 0x{offset:x}")
        struct.pack_into("<I", data, offset, new)
    return bytes(data)


if __name__ == "__main__":
    base_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    base = base_path.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for name in names():
        out = build(base, name)
        path = out_dir / f"checkra1n-kpf-pongo-j81-{name}"
        path.write_bytes(out)
        lines.append(f"{hashlib.sha256(out).hexdigest()}  {path.name}  words={len(patches(name))}")
    (out_dir / "VARIANTS.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
