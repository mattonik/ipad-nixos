#!/usr/bin/env python3
"""Capture one acknowledged, watchdog-supervised J81 PMGR page-5 register read."""
import argparse
import os
import re
import socket
import time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def capture(sock, path, module_hash, notes_hash, boot_id, supervisor_hash, runner_hash, offset, timeout=40):
    if any(not HEX.fullmatch(value) for value in (module_hash, notes_hash, supervisor_hash, runner_hash)):
        raise ValueError("invalid SHA-256")
    if not BOOT.fullmatch(boot_id) or not 1 <= timeout <= 300:
        raise ValueError("invalid boot ID or timeout")
    if offset not in (0, 4, 8):
        raise ValueError("invalid page-5 offset")
    address = f"0x{0x20e005000 + offset:x}"
    before = f"stage=before-page5-read address={address} width=32".encode()
    after = re.compile(f"stage=after-page5-read address={address} value=0x[0-9a-f]{{8}}".encode())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        command = (
            f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor_hash} '
            f'&& test "$(sha256sum /tmp/j81-page5-read-once-run | cut -d " " -f 1)" = {runner_hash} '
            f'&& /tmp/j81-page5-read-once-run --preflight {module_hash} {notes_hash} {boot_id} {offset} '
            f'&& /tmp/gpu-watchdog-supervisor --page5-read-once {module_hash} {notes_hash} {boot_id} {offset}\n'
        )
        sock.sendall(command.encode())
        expected = [
            (b"stage=before-watchdog-open", b"ARM\n"),
            (b"stage=watchdog-armed timeout=20", None),
            (before, b"READ\n"),
            (None, b"FEED 1\n"),
            (b"stage=finished rc=0", None),
            (b"stage=watchdog-disarmed", None),
        ]
        index, buffer, read_result = 0, b"", None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except (TimeoutError, socket.timeout):
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
                if wanted is None:
                    if not after.fullmatch(line):
                        raise RuntimeError("invalid page-5 read result")
                    read_result = line.decode()
                elif line != wanted:
                    raise RuntimeError("unexpected stage")
                log.write(b"host-verified " + line + b"\n")
                os.fsync(log.fileno())
                if ack:
                    if b"stage=" in buffer:
                        raise RuntimeError("pipelined stage")
                    sock.sendall(ack)
                index += 1
                if index == len(expected):
                    return read_result
        raise RuntimeError("incomplete capture; device state is unknown")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("module_sha256")
    parser.add_argument("kernel_notes_sha256")
    parser.add_argument("boot_id")
    parser.add_argument("supervisor_sha256")
    parser.add_argument("runner_sha256")
    parser.add_argument("offset", type=int, choices=(0, 4, 8))
    parser.add_argument("--timeout", type=float, default=40)
    args = parser.parse_args()
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            result = capture(sock, args.log, args.module_sha256, args.kernel_notes_sha256,
                             args.boot_id, args.supervisor_sha256, args.runner_sha256, args.offset, args.timeout)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"capture failed: {error}; do not retry this boot\n")
    print(f"captured {result}")


if __name__ == "__main__":
    main()
