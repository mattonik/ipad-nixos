#!/usr/bin/env python3
"""Capture guarded GPU ID observations; MMIO can still hang."""
import argparse
import os
from pathlib import Path
import re
import socket
import time

STAGES = (
    (b"stage=before-pmgr-read address=0x20e020320 width=32", b"pmgr-read"),
    (b"stage=before-gpc-state address=0x201e01000 width=32", b"gpc-state"),
    (b"stage=before-gpc-control address=0x201e00000 width=32", b"gpc-control"),
    (b"stage=before-gpu-revision address=0x201000020 width=32", b"gpu-revision"),
    (b"stage=before-gpu-core-id address=0x201000018 width=32", b"gpu-core-id"),
)


def capture(sock, path, binary_hash, timeout):
    """Persist each marker before acknowledging its corresponding read."""
    if not re.fullmatch(r"[0-9a-f]{64}", binary_hash):
        raise ValueError("invalid binary hash")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    buffer = b""
    stage = 0
    with os.fdopen(fd, "wb") as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        sock.sendall(f"/tmp/gpu-id-once-run {binary_hash}\n".encode())
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            log.write(chunk)
            log.flush()
            os.fsync(log.fileno())
            buffer += chunk
            if len(buffer) > 65536:
                raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip(b"\r")
                if not line.startswith(b"stage="):
                    continue
                if stage == len(STAGES) * 2:
                    if line != b"stage=finished rc=0":
                        raise RuntimeError("missing successful completion")
                    return
                index = stage // 2
                if index >= len(STAGES):
                    raise RuntimeError("unexpected extra stage")
                marker, name = STAGES[index]
                log.write(b"\nhost-stage time_ns=" + str(time.time_ns()).encode() + b" " + line + b"\n")
                log.flush()
                os.fsync(log.fileno())
                if stage % 2 == 0:
                    if line != marker:
                        raise RuntimeError("unexpected stage before checkpoint")
                    if b"stage=" in buffer:
                        raise RuntimeError("result arrived before checkpoint")
                    sock.sendall(b"READ\n")
                elif name == b"pmgr-read":
                    if line != b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0":
                        raise RuntimeError("unexpected PMGR state; GPC reads not acknowledged")
                elif not re.fullmatch(rb"stage=after-" + name + rb" raw=0x[0-9a-f]{8}", line):
                    raise RuntimeError("unexpected result after checkpoint")
                if stage % 2 and name == b"gpc-state":
                    if (int(line.rsplit(b"=", 1)[1], 16) & 0x1f) != 1:
                        raise RuntimeError("GPC state is not settled at 1; control read not acknowledged")
                if stage % 2 and name == b"gpc-control":
                    if int(line.rsplit(b"=", 1)[1], 16) & (1 << 29):
                        raise RuntimeError("GPC power-down handshake set; GPU not acknowledged")
                if stage % 2 and name == b"gpu-revision":
                    if int(line.rsplit(b"=", 1)[1], 16) in (0, 0xffffffff):
                        raise RuntimeError("invalid GPU revision; core ID not acknowledged")
                stage += 1
    raise RuntimeError("capture incomplete; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("binary_sha256")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            capture(sock, args.log, args.binary_sha256, args.timeout)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry this boot\n")
    print(f"captured GPU ID observations: {args.log}")


if __name__ == "__main__":
    main()
