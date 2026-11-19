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


def translated_base(tree, address, length):
    ranges = property_at(tree, 0x6418, b"ranges")
    bases = [parent + address - child for child, parent, span in struct.iter_unpack("<QQQ", ranges)
             if child <= address and address + length <= child + span]
    if len(bases) != 1:
        raise ValueError("expected one arm-io range covering the PMGR resource")
    return bases[0]


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
    for slot, target in [(0x588, 0xfffffff006c88488), (0x590, 0xfffffff006c884cc),
                         (0x5c8, 0xfffffff006c8872c), (0x688, 0xfffffff006c8a0c4),
                         (0x690, 0xfffffff006bcf3c8), (0x698, 0xfffffff006c8a164),
                         (0x6a8, 0xfffffff006c88df0), (0x6b8, 0xfffffff006c8a238),
                         (0x980, 0xfffffff006bd0478), (0x988, 0xfffffff006bd04f0)]:
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
                              (0x6bcd468, 0x71003d1f), (0x6bcd46c, 0x54000321),
                              # DPE group, calibration guard, four writes and parent bit update.
                              (0x6bccc74, 0xf9435d03), (0x6c88550, 0x528002c1),
                              (0x6c88554, 0x52800102), (0x6c88558, 0x52803203),
                              (0x6c88620, 0x390002a8), (0x6c8a26c, 0x340002e8),
                              (0x6c8a284, 0x97fff979), (0x6c8a29c, 0x97fff973),
                              (0x6c8a2b0, 0x97fff96e), (0x6c8a2c4, 0x97fff969),
                              (0x6c8a2d0, 0xf9436503), (0x6bcfa78, 0xd2c00108),
                              (0x6bcfaec, 0x925cf808), (0x6bcfaf4, 0xaa090103),
                              # Register group 3, dispatch soc-tvm, then read/modify/write.
                              (0x6c88510, 0x52800061), (0x6c88514, 0x52800002),
                              (0x6c88518, 0x529a0003), (0x6c8851c, 0x72a00043),
                              (0x6c88520, 0x94000a55), (0x6bccd80, 0xf9435505),
                              (0x6bccd88, 0x52800021), (0x6bccd8c, 0x14000015),
                              (0x6c88e10, 0x340001a1), (0x6c88e1c, 0xf9435d05),
                              (0x6bcf5b8, 0x54000500), (0x6bcf660, 0x34000428),
                              (0x6bcf664, 0xb9636276), (0x6bcf674, 0x97fffece),
                              (0x6bcf678, 0x121f7808), (0x6bcf67c, 0x2a140102),
                              (0x6bcf68c, 0x97fffdcd), (0x6bcf690, 0x370001d4),
                              # Group 9 registration, enableACG(true), region-zero bit update.
                              (0x6c88504, 0x529a0014), (0x6c88508, 0x72a00054),
                              (0x6c88538, 0x11401683), (0x6c88540, 0x52800121),
                              (0x6c88544, 0x52800002), (0x6c88548, 0x94000a4b),
                              (0x6bcd0e0, 0xf9434908), (0x6bcd0e8, 0x52800021),
                              (0x6bcd0ec, 0xd63f0100), (0x6bcf54c, 0xb963f275),
                              (0x6bcf55c, 0x97ffff14), (0x6bcf560, 0x121f7808),
                              (0x6bcf564, 0x2a140102), (0x6bcf580, 0x17fffe10),
                              # Page 1/4 reads, upper-pair replacement, writes and platform-active dispatch.
                              (0x6c8873c, 0x52820101), (0x6c88744, 0x940009c6),
                              (0x6c88748, 0x52a80014), (0x6c8874c, 0x52a80002),
                              (0x6c88750, 0x33007402), (0x6c88760, 0x940009c8),
                              (0x6c88768, 0x52880101), (0x6c88770, 0x940009bb),
                              (0x6c88774, 0x33007414), (0x6c88788, 0x940009be),
                              (0x6bbb7a4, 0xf942e508), (0x6bbb7ac, 0xd63f0100)]:
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
    pmgr_address, pmgr_length = registers[0]
    if (property_at(tree, 0x6efc, b"soc-tvm") != struct.pack("<I", 1)
            or struct.unpack_from("<Q", kernel, 0x247a4e8)[0] != 0xfffffff005a530d1
            or not kernel.startswith(b"soc-tvm\0", 0xeff0d1)
            or 0x6bccb60 + 4 * kernel[0xefed94] != 0x6bccd7c
            or struct.unpack_from("<Q", kernel, 0x247a0f8)[0] != 0xfffffff006bcf590
            or not kernel.startswith(b"_regGroups[kRegGroupSOCTVM].valid\0", 0xf02ed5)):
        raise ValueError("unexpected SoC TVM descriptor or dispatch")
    soc_tvm_address = translated_base(tree, pmgr_address, pmgr_length) + 0x2d000
    if 0x2d104 > pmgr_length or soc_tvm_address != 0x20e02d000:
        raise ValueError("unexpected SoC TVM address")
    print(f"soc-tvm=1 group=3 rail=1 address={soc_tvm_address:#x} request=old|1; no enable poll")
    misc_acg_offset = 0x2d000 + 0x5000
    misc_acg_address = translated_base(tree, pmgr_address, pmgr_length) + misc_acg_offset
    if (misc_acg_offset + 4 > pmgr_length or misc_acg_address != 0x20e032000
            or not kernel.startswith(b"virtual void ApplePMGR::enableACG(bool)\0", 0xf02e18)
            or not kernel.startswith(b"_regGroups[kRegGroupMiscACG].valid\0", 0xf02e40)):
        raise ValueError("unexpected MiscACG group identity or address")
    address, length = registers[resource]
    cpu_base = translated_base(tree, address, length)
    if cpu_base != 0x202220000 or length != 0x2000:
        raise ValueError("unexpected arm-io translation")
    key, = struct.unpack("<I", property_at(tree, 0x703c, b"dpe-thrtl"))
    rows = [struct.unpack_from("<I4xQ", kernel, 0xf25bd0 + 80*i) for i in range(4)]
    calibration = [value for row_key, value in rows if row_key == key]
    if (key != 12000 or calibration != [0x010e1a27333f4bff]
            or struct.unpack_from("<Q", kernel, 0x247a5c8)[0] != 0xfffffff005a53146
            or not kernel.startswith(b"dpe-thrtl\0", 0xeff146)
            or 0x6bccb60 + 4 * kernel[0xefed91 + 17] != 0x6bccc70
            or struct.unpack_from("<Q", kernel, 0x247a108)[0] != 0xfffffff006bcfa4c
            or kernel[0xefedca] != 0):
        raise ValueError("unexpected DPE throttle dispatch or calibration")
    print(f"dpe-thrtl={key} selector=8 base={cpu_base:#x} calibrated row={calibration[0]:#018x}")
    print("  write64 +0x1b0, +0x1a0, +0x150, +0x190; group 22 updates +0x190 bit 35")
    print(f"enableACG(true) group=9 region=0 instance=0 address={misc_acg_address:#x} request=old|1")
    print("startup parent calls MCC(+0x688), ACG(+0x690), voltage enable(+0x698) before the CPU table copy")
    print(f"GFX replay candidate bank={bank} lane={lane} software-state offset (instance zero)={0x19094 + gfx[3]:#x}")
    print(f"selector={selector} instance={instance} reg[{resource}]={cpu_base:#x} length={length:#x}")
    for offset in (0x78, 0x68, 0x20):
        print(f"  +{offset:#x} -> {cpu_base + offset:#x} (8 bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    try:
        check(args.kernel, args.tree)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
