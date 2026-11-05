#!/usr/bin/env python3
"""Hash the AArch64 vmlinux .notes section for comparison with /sys/kernel/notes."""
import argparse
from hashlib import sha256
from pathlib import Path
import struct


def notes(data):
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("expected little-endian ELF64 AArch64")
    shoff = struct.unpack_from("<Q", data, 40)[0]
    entsize, count, strindex = struct.unpack_from("<HHH", data, 58)
    if entsize < 64 or not count or strindex >= count or shoff > len(data) or count * entsize > len(data) - shoff:
        raise ValueError("invalid section table")
    def section(index):
        at = shoff + index * entsize
        name, kind = struct.unpack_from("<II", data, at)
        offset, size = struct.unpack_from("<QQ", data, at + 24)
        if offset > len(data) or size > len(data) - offset:
            raise ValueError("section outside file")
        return name, kind, data[offset:offset + size]
    _, kind, names = section(strindex)
    if kind != 3:
        raise ValueError("invalid section-name table")
    matches = []
    for index in range(count):
        name, kind, content = section(index)
        if name >= len(names):
            raise ValueError("invalid section name offset")
        end = names.find(b"\0", name)
        if end < 0:
            raise ValueError("unterminated section name")
        if names[name:end] == b".notes":
            if kind != 7 or not 0 < len(content) <= 1048576:
                raise ValueError("invalid .notes section")
            matches.append(content)
    if len(matches) != 1:
        raise ValueError("expected exactly one .notes section")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vmlinux", type=Path)
    args = parser.parse_args()
    try:
        print(sha256(notes(args.vmlinux.read_bytes())).hexdigest())
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid vmlinux: {error}\n")


if __name__ == "__main__":
    main()
