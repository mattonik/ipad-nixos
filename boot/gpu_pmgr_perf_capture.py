#!/usr/bin/env python3
"""Stage gpu-pmgr-perf-peek on the J81 and capture one read-only snapshot.

Reads table words at 0x20e01c000..0x20e01c0f4, control at 0x20e01c200,
and tunable at 0x20e01c300 (last byte 0x20e01c303), plus PS at
0x20e020320. Run at most once per boot. Timeout is host-side; the target
probe has no watchdog.
"""
import argparse
from collections import Counter
import hashlib
import os
from pathlib import Path
import re
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from stage_gpu_test_bundle import stage  # noqa: E402

HOST = "172.16.42.1"
REMOTE = "/tmp/gpu-pmgr-perf-peek"
READY = b"stage=before-perf-read base=0x20e01c000 words=34 ps=0x20e020320"
DONE = b"stage=after-perf-read"
LINE = re.compile(rb"(ps|ctl|perf-tunable|perf\d\d(?:-p4)?) raw=0x([0-9a-f]{8})")
EXPECTED = {"ps", "ctl", "perf-tunable"} | {
    f"perf{n:02d}{suffix}" for n in range(16) for suffix in ("", "-p4")
}


def complete_output(data):
    names = Counter(name.decode() for name, _ in LINE.findall(data))
    return names == Counter({name: 1 for name in EXPECTED})


def decode(log: bytes) -> None:
    for name, raw in LINE.findall(log):
        v = int(raw, 16)
        name = name.decode()
        if name.startswith("perf") and name[4:6].isdigit():
            if name.endswith("-p4"):
                print(f"{name} 0x{v:08x}")
                continue
            fb, pre, post = (v >> 12) & 0x1ff, (v >> 4) & 0x1f, v & 0xf
            mhz = 24 * fb / (pre * (post + 1)) if pre else 0
            print(f"{name} 0x{v:08x} fb={fb} pre={pre} post={post} ~{mhz:.1f} MHz vidx={v >> 24}")
        elif name == "ps":
            print(f"ps    0x{v:08x} target={v & 0xf} actual={(v >> 4) & 0xf}")
        elif name == "perf-tunable":
            print(f"{name} 0x{v:08x}")
        else:
            print(f"ctl   0x{v:08x} bit31={v >> 31}")


def capture(sock, path, timeout):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    data, acknowledged = b"", False
    with os.fdopen(fd, "wb") as log:
        sock.sendall(REMOTE.encode() + b"\n")
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            log.write(chunk)
            log.flush()
            os.fsync(log.fileno())
            data += chunk
            if len(data) > 65536:
                raise RuntimeError("capture exceeded 64 KiB")
            if not acknowledged and READY in data:
                sock.sendall(b"READ\n")
                acknowledged, data = True, b""
                continue
            if acknowledged and DONE in data:
                if not complete_output(data):
                    raise RuntimeError("capture completed without exactly one value for every expected register")
                return data
    raise RuntimeError("capture incomplete; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="static aarch64 gpu-pmgr-perf-peek")
    parser.add_argument("sha256", help="expected sha256 of the binary")
    parser.add_argument("log", type=Path, help="new private host log file")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("--timeout must be between 1 and 300 seconds")
    data = args.binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != args.sha256:
        parser.error("binary hash mismatch; not staging")
    stage(HOST, REMOTE, data)
    try:
        with socket.create_connection((HOST, 23), timeout=5) as sock:
            time.sleep(0.25)
            out = capture(sock, args.log, args.timeout)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry in this boot\n")
    print(f"captured: {args.log}")
    decode(out)


if __name__ == "__main__":
    main()
