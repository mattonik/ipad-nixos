#!/usr/bin/env python3
"""Rebuild smaller Apple HBPP data packets from the already-exported J81 firmware packet; never contacts hardware.

The format is the one Apple's driver builds (research/2026-10-12-touch-4cb1-analysis.md, section 2): `18 e1`, `30 01`, payload length in 32-bit words (big-endian 16 bit),
destination address with its 16-bit halves swapped, a big-endian 16-bit byte sum of those six bytes, the payload (already in wire order here), and a 32-bit byte sum of the
payload with its halves swapped. `parse()` validates a packet against that format; `rebuild()` cuts a slice out of a validated packet's payload and wraps it as a new packet
whose destination is the slice's byte offset (Apple's unconstructed pattern). Rebuilding the full payload at offset 0 must reproduce the original packet bit for bit, which
is checked on every call, so a wrong format is caught offline and nothing private is ever printed (only lengths, offsets and verdicts).

  boot/touch_fw_rebuild.py PACKET_FILE OUT_DIR SIZE[@OFFSET | ->DEST] [...]   (->DEST: the first SIZE payload bytes with destination DEST)
"""
import argparse
import os
import pathlib
import stat
import sys


def hdr_sum(body):
    return sum(body) & 0xFFFF


def swap_halves32(v):
    return ((v & 0xFFFF) << 16) | (v >> 16)


def addr_bytes(addr):
    """32-bit value as Apple emits it: the 16-bit halves swapped, each half big-endian."""
    v = swap_halves32(addr)
    return v.to_bytes(4, "big")


def build(payload, addr):
    if len(payload) % 4 or not payload:
        raise ValueError("payload length must be a non-zero multiple of 4")
    if len(payload) > 0xFFF0:
        raise ValueError("payload above the 0xfff0 firmware limit")
    body = (len(payload) // 4).to_bytes(2, "big") + addr_bytes(addr)
    trailer = swap_halves32(sum(payload) & 0xFFFFFFFF).to_bytes(4, "big")
    return b"\x18\xe1\x30\x01" + body + hdr_sum(body).to_bytes(2, "big") + payload + trailer


def parse(packet):
    """Return (payload, address) if @packet is exactly one valid packet, else raise ValueError."""
    if len(packet) < 16 or packet[:4] != b"\x18\xe1\x30\x01":
        raise ValueError("not a data packet")
    words = int.from_bytes(packet[4:6], "big")
    if len(packet) != words * 4 + 16:
        raise ValueError("length field does not match the packet size")
    if int.from_bytes(packet[10:12], "big") != hdr_sum(packet[4:10]):
        raise ValueError("header sum mismatch")
    payload = packet[12:-4]
    if packet[-4:] != swap_halves32(sum(payload) & 0xFFFFFFFF).to_bytes(4, "big"):
        raise ValueError("payload sum mismatch")
    addr = swap_halves32(int.from_bytes(packet[6:10], "big"))
    return payload, addr


def rebuild(packet, size, offset=0):
    payload, addr = parse(packet)
    if build(payload, addr) != packet:
        raise ValueError("self-check failed: the packet is not reproduced from its own fields")
    if size % 4 or offset % 4 or offset + size > len(payload):
        raise ValueError("size and offset must be multiples of 4 inside the payload")
    return build(payload[offset:offset + size], addr + offset)


def rebuild_to(packet, size, dest):
    """The first @size payload bytes of a validated packet, re-wrapped with destination @dest (for the destination tests; the payload content is unchanged)."""
    payload, addr = parse(packet)
    if build(payload, addr) != packet:
        raise ValueError("self-check failed: the packet is not reproduced from its own fields")
    if size % 4 or size > len(payload) or dest % 4:
        raise ValueError("size and destination must be multiples of 4, size inside the payload")
    return build(payload[:size], dest)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packet", type=pathlib.Path)
    ap.add_argument("out_dir", type=pathlib.Path)
    ap.add_argument("slices", nargs="+", help="SIZE or SIZE@OFFSET in bytes (multiples of 4)")
    a = ap.parse_args(argv)
    packet = a.packet.read_bytes()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for item in a.slices:
        if "->" in item:
            size, _, dest = item.partition("->")
            out = rebuild_to(packet, int(size, 0), int(dest, 0))
            path = a.out_dir / f"pkt-{int(size, 0)}-to-{int(dest, 0):#x}.bin"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(fd, "wb") as f:
                f.write(out)
            print(f"{path.name}: {len(out)} bytes (payload {int(size, 0)}, destination {int(dest, 0):#x})")
            continue
        size, _, off = item.partition("@")
        out = rebuild(packet, int(size, 0), int(off, 0) if off else 0)
        path = a.out_dir / f"pkt-{int(size, 0)}@{int(off, 0) if off else 0}.bin"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb") as f:
            f.write(out)
        print(f"{path.name}: {len(out)} bytes (payload {int(size, 0)} at offset {int(off, 0) if off else 0})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
