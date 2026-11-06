#!/usr/bin/env python3
"""Capture a single GFX power attempt after a host-persisted checkpoint."""
import argparse
import os
from pathlib import Path
import re
import socket
import time

HEX = re.compile(r"[0-9a-f]{64}\Z")
DONE = re.compile(rb"(?:^|\n)stage=after-gfx-power rc=([0-9]+)\r?\n")
PEEK_READY = b"stage=before-pmgr-read address=0x20e020320 width=32"
PEEK_DONE = re.compile(rb"(?:^|\n)stage=after-pmgr-read raw=(0x[0-9a-f]{8}) target=(\d+) actual=(\d+) auto=([01]) reset=([01])\r?\n")


def capture(sock, path, module_hash, notes_hash, timeout):
    if not HEX.fullmatch(module_hash) or not HEX.fullmatch(notes_hash):
        raise ValueError("expected lowercase SHA-256 values")
    ready = (f"stage=before-gfx-power module={module_hash} kernel_notes={notes_hash}").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    data = b""
    stage = 0
    with os.fdopen(fd, "wb") as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        sock.sendall(f"/tmp/gpu-pmgr-once-run {module_hash} {notes_hash}\n".encode())
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
            if stage < 3 and DONE.search(data):
                raise RuntimeError("completion arrived before checkpoint")
            while True:
                if stage == 0:
                    if PEEK_DONE.search(data):
                        raise RuntimeError("PMGR result arrived before checkpoint")
                    marker = re.search(rb"(?:^|\n)" + re.escape(PEEK_READY) + rb"\r?\n", data)
                    if not marker:
                        break
                    data = data[marker.end():]
                    sock.sendall(b"READ\n")
                    stage = 1
                elif stage == 1:
                    result = PEEK_DONE.search(data)
                    if not result:
                        break
                    if result.groups() != (b"0x00000300", b"0", b"0", b"0", b"0"):
                        raise RuntimeError("unexpected starting PMGR state; no power request sent")
                    data = data[result.end():]
                    stage = 2
                elif stage == 2:
                    marker = re.search(rb"(?:^|\n)" + re.escape(ready) + rb"\r?\n", data)
                    if not marker:
                        break
                    data = data[marker.end():]
                    sock.sendall(b"POWER\n")
                    stage = 3
                else:
                    result = DONE.search(data)
                    if not result:
                        break
                    if result.group(1) != b"0":
                        raise RuntimeError("power attempt failed; device state is unknown")
                    return
    raise RuntimeError("capture incomplete; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="new private host log")
    parser.add_argument("module_sha256")
    parser.add_argument("kernel_notes_sha256")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    if not HEX.fullmatch(args.module_sha256) or not HEX.fullmatch(args.kernel_notes_sha256):
        parser.error("hashes must be lowercase SHA-256")
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            capture(sock, args.log, args.module_sha256, args.kernel_notes_sha256, args.timeout)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry in this boot\n")
    print(f"captured GFX power attempt: {args.log}")


if __name__ == "__main__":
    main()
