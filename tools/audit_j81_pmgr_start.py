#!/usr/bin/env python3
"""Check the startup mapping and GFX software-state producers in J81AP 19H394."""
import argparse
import hashlib
from pathlib import Path
import struct


def checked_file(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{path.name}: unexpected decompressed 19H394 file")
    return data


def property_at(tree, offset, name):
    field, size = struct.unpack_from("<32sI", tree, offset - 36)
    if field.rstrip(b"\0") != name:
        raise ValueError(f"expected property {name!r} before {offset:#x}")
    return tree[offset:offset + (size & 0xffffff)]


def check_gfx_producers(kernel, devices, gfx):
    # All records in this pinned tree use the byte-ID layout. A zero ends the parent list.
    rows = [row for row, in struct.iter_unpack("48s", devices)]
    if len(rows) != 98 or any(row[26:28] != b"\0\0" for row in rows):
        raise ValueError("unexpected PMGR device table layout")
    children = [row[32:].rstrip(b"\0") for row in rows if gfx[3] in row[4:8].split(b"\0")[0]]
    if gfx[0] or gfx[2] or gfx[15] or any(gfx[4:8]) or children:
        raise ValueError("unexpected GFX seed flags or dependency edge")

    # Enumerate PC-relative B and BL instructions in __PLK_TEXT_EXEC, including tail calls.
    text_start = 0x5a9c000
    code = memoryview(kernel)[0xf48000:0xf48000 + 0x1258000]
    target = 0x6bc8de4
    callers = []
    for i, (word,) in enumerate(struct.iter_unpack("<I", code)):
        if word & 0x7c000000 == 0x14000000:
            pc = text_start + 4 * i
            if (word & 0x3ffffff) == ((target - pc) // 4 & 0x3ffffff):
                callers.append(pc)
    if callers != [0x6bc3bd0, 0x6bc9210, 0x6bd0434, 0x6bd7c18]:
        raise ValueError(f"unexpected direct callers of the state builder: {callers!r}")
    word_offset = 4 * (gfx[3] // 32)
    print(f"GFX seed word={0x18aa4 + word_offset:#x} mask={1 << (gfx[3] % 32):#x} "
          f"record[0]={gfx[0]:#x} record[15]={gfx[15]:#x} children={len(children)}/{len(rows)}")
    print("aggregate builder direct branch sites: " + ", ".join(hex(pc) for pc in callers))


def check(kernel_path, tree_path):
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    tree = checked_file(tree_path, "be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003")
    # File offsets are specific to the two digest-checked inputs.
    for slot, target in [(0x588, 0xfffffff006c88488), (0x5c8, 0xfffffff006c8872c),
                         (0x688, 0xfffffff006c8a0c4), (0x698, 0xfffffff006c8a164),
                         (0x980, 0xfffffff006bd0478)]:
        if struct.unpack_from("<Q", kernel, 0x24929c0 + slot)[0] != target:
            raise ValueError(f"unexpected PMGR method in slot {slot:#x}")
    # The subclass uses the parent vtable address point with its two-word ABI header.
    parent = struct.unpack_from("<Q", kernel, 0x2491dc0)[0]
    if parent != 0xfffffff006fcda40 or struct.unpack_from("<Q", kernel, 0x247a018)[0] != 0xfffffff006bccefc:
        raise ValueError("unexpected startup parent dispatch")
    # Parent dispatch, low-nibble read, seed gates, aggregate store and replay comparison.
    for address, expected in [(0x6c88794, 0xf942ed08), (0x6c8879c, 0xd63f0100),
                              (0x6bccf34, 0xf9434508), (0x6bccf38, 0x52800021),
                              (0x6bccf3c, 0xd63f0100), (0x6bcd0f4, 0xf9434d08),
                              (0x6bcd0fc, 0x52800021), (0x6bcd100, 0xd63f0100),
                              (0x6c887cc, 0xb340dc14), (0x6bc6c9c, 0x12000c00),
                              (0x6bc2a04, 0x71003c1f), (0x6bc2a6c, 0x360000c8),
                              (0x6bc2a70, 0x340000b8), (0x6bc2a80, 0x9400104e),
                              (0x6bc2778, 0x362000c9), (0x6bc3bb0, 0x34000140),
                              (0x6bc3bd4, 0x383a6a79), (0x6bc9118, 0x54000b20),
                              (0x6bc924c, 0x3900011a), (0x6bcd464, 0x38796908),
                              (0x6bcd468, 0x71003d1f), (0x6bcd46c, 0x54000321)]:
        file_offset = 0x21344b0 + address - 0x6c884b0
        if struct.unpack_from("<I", kernel, file_offset)[0] != expected:
            raise ValueError(f"unexpected instruction at address suffix {address:x}")
    devices = property_at(tree, 0x74f8, b"devices")
    gfx, = [devices[i:i+48] for i in range(0, len(devices), 48)
            if devices[i+32:i+36] == b"GFX\0"]
    check_gfx_producers(kernel, devices, gfx)
    lane, bank = gfx[10:12]
    region, base, enabled = struct.unpack_from("<III", property_at(tree, 0x6a1c, b"ps-regs"), bank * 12)
    if (gfx[3], bank, lane, region, base + 8 * lane) != (0x7c, 3, 4, 0, 0x20320) or not enabled & (1 << lane):
        raise ValueError("GFX replay lane mismatch")
    args = struct.unpack_from("<4I", kernel, 0x21344b0)
    for opcode, register in zip(args, (1, 2, 3, 4)):
        if opcode & 0xffe0001f != 0x52800000 | register:
            raise ValueError("expected MOVZ W-register mapper argument")
    selector, resource, instance, options = [(opcode >> 5) & 0xffff for opcode in args]
    if (selector, resource, instance, options) != (8, 1, 0, 0):
        raise ValueError("unexpected mapper arguments")

    registers = list(struct.iter_unpack("<QQ", property_at(tree, 0x8808, b"reg")))
    address, length = registers[resource]
    bases = [parent + address - child for child, parent, span in
             struct.iter_unpack("<QQQ", property_at(tree, 0x6418, b"ranges"))
             if child <= address and address + length <= child + span]
    if bases != [0x202220000] or length != 0x2000:
        raise ValueError("unexpected arm-io translation")
    print("startup parent resolves MCC(+0x688) then voltage enable(+0x698) before the CPU table copy")
    print(f"GFX replay candidate bank={bank} lane={lane} software-state offset (instance zero)={0x19094 + gfx[3]:#x}")
    print(f"selector={selector} instance={instance} reg[{resource}]={bases[0]:#x} length={length:#x}")
    for offset in (0x78, 0x68, 0x20):
        print(f"  +{offset:#x} -> {bases[0] + offset:#x} (8 bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    try:
        check(args.kernel, args.tree)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
