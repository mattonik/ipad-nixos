#!/usr/bin/env python3
"""Exercise ELF .notes selection on synthetic files."""
import struct
from kernel_notes_sha256 import notes

data = bytearray(320)
data[:6] = b"\x7fELF\x02\x01"
struct.pack_into("<H", data, 18, 183)
struct.pack_into("<Q", data, 40, 64)
struct.pack_into("<HHH", data, 58, 64, 3, 1)
names = b"\0.shstrtab\0.notes\0"
data[256:256 + len(names)] = names
data[288:292] = b"note"
struct.pack_into("<II", data, 128, 1, 3)
struct.pack_into("<QQ", data, 152, 256, len(names))
struct.pack_into("<II", data, 192, 11, 7)
struct.pack_into("<QQ", data, 216, 288, 4)
assert notes(data) == b"note"
for offset, value in ((18, 0), (60, 0), (192, 0), (216, 255)):
    bad = bytearray(data)
    bad[offset] = value
    if offset == 216:
        bad[offset:offset + 8] = struct.pack("<Q", len(data))
    try:
        notes(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"bad ELF at {offset} accepted")
print("PASS: ELF notes selection and malformed sections")
