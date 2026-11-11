#!/usr/bin/env python3
"""Check instruction signatures for the proposed 19H394 GPC timer hook."""
import argparse
from pathlib import Path
import struct

GPC = struct.pack('<6I', 0x52800228, 0xb9100008, 0xb9500008,
                  0x3727ffe8, 0x52800140, 0x9400b575)
MACH_TIME = bytes.fromhex(
    '88d038d5 09c540f9 2b2d40f9 e9030baa df3f03d5 4ae03bd5 '
    '0bc540f9 6b2d40f9 7f0109eb 41ffff54 4001098b c0035fd6 '
    '88d038d5 09c540f9 2b2d40f9 e9030baa')


def locate(data, pattern):
    hits = []
    start = 0
    while (pos := data.find(pattern, start)) != -1:
        hits.append(pos)
        start = pos + 1
    if len(hits) != 1 or hits[0] % 4:
        raise ValueError(f'expected one aligned signature, got {len(hits)}')
    return hits[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path, help='decoded kernel image')
    args = parser.parse_args()
    data = args.kernel.read_bytes()
    for name, pattern in [('GPC sequence', GPC), ('mach_absolute_time', MACH_TIME)]:
        print(f'{name}: unique signature at file offset 0x{locate(data, pattern):x}')
    print('Offline signature check only; verify UUID, addresses and hook context separately.')


if __name__ == '__main__':
    main()
