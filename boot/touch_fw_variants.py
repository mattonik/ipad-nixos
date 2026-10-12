#!/usr/bin/env python3
"""Build deliberately malformed variants of the J81 data packet for the ROM-behaviour tests (research/2026-10-12-touch-rom-states.md, change list items 1 and 2).

Never contacts hardware. All sizes are totals on the wire; each variant keeps the 18 e1 frame header and 4-byte alignment so touch-diag accepts it. Kinds:
  zero SIZE          18 e1 followed by zeros (zeroed header and payload)
  badsum SIZE        a valid packet of SIZE bytes (cut from the real payload) whose 16-bit header sum is wrong
  declared SIZE W    SIZE clocked bytes whose header declares W 32-bit words (header sum correct for the declared length)
Destination is always 0; no packet uses another address.

  boot/touch_fw_variants.py PACKET_FILE OUT_DIR
"""
import argparse
import os
import pathlib
import stat
import sys

import touch_fw_rebuild as r


def zero(size):
    return b"\x18\xe1" + bytes(size - 2)


def badsum(real, size):
    pkt = bytearray(r.rebuild(real, size - 16, 0))
    pkt[10] ^= 0xFF                               # corrupt the big-endian header sum
    return bytes(pkt)


def declared(real, size, words):
    payload = r.parse(real)[0]
    body = words.to_bytes(2, "big") + r.addr_bytes(0)
    pkt = b"\x18\xe1\x30\x01" + body + r.hdr_sum(body).to_bytes(2, "big")
    pkt += (payload * (size // len(payload) + 1))[:size - len(pkt)]
    return pkt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packet", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    a = ap.parse_args(argv)
    real = a.packet.read_bytes()
    r.parse(real)
    variants = {
        "zero-8208": zero(8208), "zero-18448": zero(18448),
        "badsum-8208": badsum(real, 8208), "badsum-18448": badsum(real, 18448),
        "declared-80-as-14818w": declared(real, 80, 14818), "declared-59288-as-16w": declared(real, 59288, 16),
    }
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name, pkt in variants.items():
        assert len(pkt) % 4 == 0 and pkt[:2] == b"\x18\xe1", name
        fd = os.open(a.out_dir / f"var-{name}.bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as f:
            f.write(pkt)
        print(f"var-{name}.bin: {len(pkt)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
