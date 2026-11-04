#!/usr/bin/env python3
"""Capture the fixed PMGR observation over the J81 control telnet shell."""
import argparse
import os
from pathlib import Path
import re
import socket
import time

READY = b"stage=before-pmgr-read address=0x20e020320 width=32"
DONE = re.compile(rb"stage=after-pmgr-read raw=0x[0-9a-f]{8} target=\d+ actual=\d+ auto=[01] reset=[01]\r?\n")


def capture(sock, path, timeout):
    """Acknowledge the read only after the host has persisted its marker."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    data = b""
    acknowledged = False
    with os.fdopen(fd, "wb") as log:
        sock.sendall(b"/tmp/gpu-pmgr-peek\n")
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
                acknowledged = True
                data = b""
                continue
            if acknowledged and DONE.search(data):
                return
    raise RuntimeError("capture incomplete; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="new private host log file")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            capture(sock, args.log, args.timeout)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry in this boot\n")
    print(f"captured PMGR observation: {args.log}")


if __name__ == "__main__":
    main()
