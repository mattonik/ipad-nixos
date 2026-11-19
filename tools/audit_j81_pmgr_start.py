#!/usr/bin/env python3
"""Check the selector-8 startup mapping in the decompressed J81AP 19H394 files."""
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


def check(kernel_path, tree_path):
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    tree = checked_file(tree_path, "be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003")
    # File offsets are specific to the two digest-checked inputs.
    for slot, target in [(0x588, 0xfffffff006c88488), (0x5c8, 0xfffffff006c8872c),
                         (0x688, 0xfffffff006c8a0c4), (0x698, 0xfffffff006c8a164)]:
        if struct.unpack_from("<Q", kernel, 0x24929c0 + slot)[0] != target:
            raise ValueError(f"unexpected PMGR method in slot {slot:#x}")
    # The subclass uses the parent vtable address point with its two-word ABI header.
    parent = struct.unpack_from("<Q", kernel, 0x2491dc0)[0]
    if parent != 0xfffffff006fcda40 or struct.unpack_from("<Q", kernel, 0x247a018)[0] != 0xfffffff006bccefc:
        raise ValueError("unexpected startup parent dispatch")
    # Validate the instructions that select the parent, MCC and voltage-manager methods.
    for address, expected in [(0x6c88794, 0xf942ed08), (0x6c8879c, 0xd63f0100),
                              (0x6bccf34, 0xf9434508), (0x6bccf38, 0x52800021),
                              (0x6bccf3c, 0xd63f0100), (0x6bcd0f4, 0xf9434d08),
                              (0x6bcd0fc, 0x52800021), (0x6bcd100, 0xd63f0100),
                              (0x6c887cc, 0xb340dc14)]:
        file_offset = 0x21344b0 + address - 0x6c884b0
        if struct.unpack_from("<I", kernel, file_offset)[0] != expected:
            raise ValueError(f"unexpected instruction at address suffix {address:x}")
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
