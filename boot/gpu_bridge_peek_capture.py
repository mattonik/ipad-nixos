#!/usr/bin/env python3
"""Capture one supervised, read-only J81 bridge peek with strict checkpoints."""
import argparse
import os
import re
import socket
import time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
PMGR_BEFORE = b"stage=before-pmgr-read address=0x20e020320 width=32"
PMGR_AFTER = b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0"


def _hash(value, name):
    if not HEX.fullmatch(value):
        raise ValueError(f"invalid {name} hash")


def capture(sock, path, binary_sha256, supervisor_sha256, wrapper_sha256, timeout=40):
    for value, name in ((binary_sha256, "probe"), (supervisor_sha256, "supervisor"),
                        (wrapper_sha256, "wrapper")):
        _hash(value, name)
    if not 1 <= timeout <= 300:
        raise ValueError("timeout must be between 1 and 300 seconds")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    result = None
    with os.fdopen(fd, "wb", buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        command = (
            f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor_sha256} '
            f'&& test "$(sha256sum /tmp/gpu-bridge-peek-run | cut -d " " -f 1)" = {wrapper_sha256} '
            f'&& /tmp/gpu-watchdog-supervisor --bridge-peek {binary_sha256}\n'
        )
        sock.sendall(command.encode())
        expected = [
            (b"stage=before-watchdog-open", b"ARM\n"),
            (b"stage=watchdog-armed timeout=20", None),
            (PMGR_BEFORE, b"READ\n"),
            (PMGR_AFTER, b"FEED 1\n"),
            (b"stage=before-gpc-state address=0x201e01000 op=read value=0x00000000", b"ACCESS\n"),
            (None, b"FEED 2\n"),
            (b"stage=before-bridge-peek address=0x201f00018 op=read value=0x00000000", b"ACCESS\n"),
            (None, b"FEED 3\n"),
            (b"stage=finished rc=0", None),
            (b"stage=watchdog-disarmed", None),
        ]
        index, buffer = 0, b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            log.write(chunk)
            os.fsync(log.fileno())
            buffer += chunk
            if len(buffer) > 65536:
                raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip(b"\r")
                if not line.startswith(b"stage="):
                    continue
                if index >= len(expected):
                    raise RuntimeError("unexpected stage")
                wanted, ack = expected[index]
                if wanted is not None and line != wanted:
                    raise RuntimeError("unexpected stage")
                if wanted is None:
                    if index == 5 and not re.fullmatch(rb"stage=after-gpc-state value=0x[0-9a-f]{8}", line):
                        raise RuntimeError("invalid GPC result")
                    if index == 7:
                        match = re.fullmatch(rb"stage=after-bridge-peek value=0x([0-9a-f]{8})", line)
                        if not match:
                            raise RuntimeError("invalid bridge result")
                        result = match.group(1).decode()
                log.write(b"host-verified " + line + b"\n")
                os.fsync(log.fileno())
                if ack:
                    if b"stage=" in buffer:
                        raise RuntimeError("pipelined stage")
                    sock.sendall(ack)
                index += 1
                if index == len(expected):
                    return result
        raise RuntimeError("incomplete capture; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("probe_sha256")
    parser.add_argument("supervisor_sha256")
    parser.add_argument("wrapper_sha256")
    parser.add_argument("--timeout", type=float, default=40)
    args = parser.parse_args()
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            value = capture(sock, args.log, args.probe_sha256, args.supervisor_sha256,
                            args.wrapper_sha256, args.timeout)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry this boot\n")
    print(f"Bridge peek completed: 0x{value}")


if __name__ == "__main__":
    main()
