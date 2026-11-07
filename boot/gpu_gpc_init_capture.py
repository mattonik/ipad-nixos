#!/usr/bin/env python3
"""Checkpoint GPC init; not a hardware-safety qualification."""
import argparse
import os
from pathlib import Path
import re
import socket
import time

PMGR_BEFORE = b"stage=before-pmgr-read address=0x20e020320 width=32"
PMGR_AFTER = b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0"
FIXED = (
    ("initial-state", 0x1000, "read", 0),
    ("setup-mask", 0x10000, "write", 0xffff0000),
    ("setup-control", 0, "write", 0x40000000),
    ("request-state", 0x1000, "write", 0x11),
)


def capture(sock, path, binary_hash, timeout, supervised=False, supervisor_hash=None, wrapper_hash=None):
    if not re.fullmatch(r"[0-9a-f]{64}", binary_hash):
        raise ValueError("invalid binary hash")
    if supervised and any(not value or not re.fullmatch(r"[0-9a-f]{64}", value) for value in (supervisor_hash, wrapper_hash)):
        raise ValueError("invalid supervisor or wrapper hash")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    stage, poll, buffer, watchdog_stage, feeds = 0, 0, b"", 0, 0
    with os.fdopen(fd, "wb") as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if supervised:
            command = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor_hash} && '
                       f'test "$(sha256sum /tmp/gpu-gpc-init-cycle-run | cut -d " " -f 1)" = {wrapper_hash} && '
                       f"/tmp/gpu-watchdog-supervisor --gpc-init-cycle {binary_hash}\n")
        else:
            command = f"/tmp/gpu-gpc-init-run {binary_hash}\n"
        sock.sendall(command.encode())
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
                log.write(b"\nhost-stage time_ns=" + str(time.time_ns()).encode() + b" " + line + b"\n")
                log.flush()
                os.fsync(log.fileno())
                if supervised and watchdog_stage < 2:
                    if watchdog_stage == 0 and line == b"stage=before-watchdog-open":
                        sock.sendall(b"ARM\n"); watchdog_stage = 1; continue
                    if watchdog_stage == 1 and line == b"stage=watchdog-armed timeout=20":
                        watchdog_stage = 2; continue
                    raise RuntimeError("unexpected watchdog checkpoint")
                if supervised and watchdog_stage == 3:
                    if line != b"stage=watchdog-disarmed": raise RuntimeError("watchdog not disarmed")
                    return value
                if supervised and watchdog_stage == 4:
                    if line != b"stage=watchdog-disarmed": raise RuntimeError("watchdog not disarmed")
                    return value
                if stage == 0:
                    if line != PMGR_BEFORE or b"stage=" in buffer:
                        raise RuntimeError("unexpected PMGR checkpoint")
                    sock.sendall(b"READ\n")
                    stage = 1
                    continue
                if stage == 1:
                    if line != PMGR_AFTER:
                        raise RuntimeError("unexpected PMGR state")
                    stage = 2
                    if supervised:
                        feeds += 1; sock.sendall(f"FEED {feeds}\n".encode())
                    continue
                if stage == 1000:
                    if line != b"stage=finished rc=0":
                        raise RuntimeError("missing successful completion")
                    if supervised:
                        watchdog_stage = 3; continue
                    return value
                index = (stage - 2) // 2
                if index < len(FIXED):
                    name, offset, operation, expected = FIXED[index]
                else:
                    name, offset, operation, expected = f"poll-{poll:02d}", 0x1000, "read", 0
                before = f"stage=before-{name} address=0x{0x201e00000 + offset:x} op={operation} value=0x{expected:08x}".encode()
                if stage % 2 == 0:
                    if line != before or b"stage=" in buffer:
                        raise RuntimeError("unexpected checkpoint or pipelined result")
                    sock.sendall(b"ACCESS\n")
                else:
                    match = re.fullmatch(rb"stage=after-" + name.encode() + rb" value=0x([0-9a-f]{8})", line)
                    if not match:
                        raise RuntimeError("unexpected access result")
                    value = int(match.group(1), 16)
                    if index < len(FIXED) and value != expected:
                        raise RuntimeError("initial state or write confirmation mismatch")
                    if index >= len(FIXED):
                        if value & 0x10:
                            poll += 1
                            if poll >= 64:
                                raise RuntimeError("GPC poll limit reached")
                            stage -= 2
                        elif value & 0xf != 1:
                            raise RuntimeError("GPC reached unexpected state")
                        else:
                            stage = 1000
                            if supervised:
                                feeds += 1; sock.sendall(f"FEED {feeds}\n".encode())
                            continue
                    if supervised:
                        feeds += 1; sock.sendall(f"FEED {feeds}\n".encode())
                stage += 1
    raise RuntimeError("capture incomplete; hardware state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("binary_sha256")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--supervised", action="store_true")
    parser.add_argument("--supervisor-sha256")
    parser.add_argument("--wrapper-sha256")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300 seconds")
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            result = capture(sock, args.log, args.binary_sha256, args.timeout, args.supervised,
                             args.supervisor_sha256, args.wrapper_sha256)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry this boot\n")
    print(f"GPC state readback: 0x{result:08x}; capture: {args.log}")


if __name__ == "__main__":
    main()
