#!/usr/bin/env python3
"""Capture one supervised GPC initialization and timed J81 core revision read."""
import argparse
import os
import re
import socket
import time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
STAGES = (
    b"stage=before-pmgr-read address=0x20e020320 width=32",
    b"stage=before-pmgr-read address=0x20e020320 width=32",
    b"stage=before-gpc-state address=0x201e01000 width=32",
    b"stage=before-timed-sequence address=0x201000020 width=32",
)


def capture(sock, path, probe_hash, timeout, supervisor_hash, wrapper_hash):
    if not all(HEX.fullmatch(x or "") for x in (probe_hash, supervisor_hash, wrapper_hash)):
        raise ValueError("invalid SHA-256")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        command = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor|cut -d " " -f1)" = {supervisor_hash} && '
                   f'test "$(sha256sum /tmp/gpu-core-revision-once-cycle-run|cut -d " " -f1)" = {wrapper_hash} && '
                   f"/tmp/gpu-watchdog-supervisor --core-revision-cycle {probe_hash}\n")
        sock.sendall(command.encode())
        buf = b""
        stage = watchdog = feeds = 0
        values = {}
        echoes = set()
        awaiting = False
        disarming = False
        poll_ok = core_armed = False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            log.write(chunk)
            os.fsync(log.fileno())
            buf += chunk
            if len(buf) > 65536:
                raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip(b"\r")
                if line in echoes:
                    echoes.remove(line)
                    continue
                if line.startswith(b"checkpoint=gpc-poll-ok "):
                    match = re.fullmatch(rb"checkpoint=gpc-poll-ok raw=0x([0-9a-f]{8}) polls=([0-9]+)", line)
                    if stage != 3 or not awaiting or poll_ok or not match or int(match[1], 16) & 0x1f != 1 or not 1 <= int(match[2]) <= 1000:
                        raise RuntimeError("invalid GPC poll checkpoint")
                    poll_ok = True
                    continue
                if line == b"checkpoint=before-gpu-revision":
                    if stage != 3 or not awaiting or not poll_ok or core_armed:
                        raise RuntimeError("unexpected core-read checkpoint")
                    core_armed = True
                    continue
                if not line.startswith(b"stage="):
                    continue
                if watchdog == 0:
                    if line != b"stage=before-watchdog-open": raise RuntimeError("missing watchdog arm checkpoint")
                    echoes.add(b"ARM"); sock.sendall(b"ARM\n"); watchdog = 1; continue
                if watchdog == 1:
                    if line != b"stage=watchdog-armed timeout=20": raise RuntimeError("watchdog did not arm")
                    watchdog = 2; continue
                if disarming:
                    if line != b"stage=watchdog-disarmed": raise RuntimeError("watchdog not disarmed")
                    if b"stage=" in buf: raise RuntimeError("unexpected stage after watchdog disarm")
                    return values
                if line.startswith(b"stage=before-"):
                    if awaiting or stage >= len(STAGES) or line != STAGES[stage] or b"stage=" in buf:
                        raise RuntimeError("unexpected or pipelined checkpoint")
                    echoes.add(b"READ"); sock.sendall(b"READ\n"); awaiting = True
                elif line.startswith(b"stage=after-"):
                    if not awaiting or b"stage=" in buf: raise RuntimeError("unexpected or pipelined read result")
                    names = (b"pmgr-read", b"pmgr-read", b"gpc-state", b"timed-sequence")
                    if not line.startswith(b"stage=after-" + names[stage] + b" "):
                        raise RuntimeError("read result does not match checkpoint")
                    if stage == 0 and line != b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0":
                        raise RuntimeError("PMGR domain is not fully active")
                    if stage == 1 and line != b"stage=after-pmgr-read raw=0x000003ff":
                        raise RuntimeError("PMGR domain is not fully active")
                    if stage == 2 and line != b"stage=after-gpc-state raw=0x00000000":
                        raise RuntimeError("GPC state is not settled")
                    if stage == 3:
                        if not core_armed: raise RuntimeError("missing pre-read checkpoints")
                        match = re.fullmatch(rb"stage=after-timed-sequence raw=0x([0-9a-f]{8})", line)
                        if not match or int(match.group(1), 16) in (0, 0xffffffff):
                            raise RuntimeError("invalid GPU revision")
                        values["gpu-revision"] = int(match.group(1), 16)
                    stage += 1; awaiting = False
                    feeds += 1; echo = f"FEED {feeds}".encode(); echoes.add(echo); sock.sendall(echo + b"\n")
                elif line == b"stage=finished rc=0":
                    if stage != len(STAGES) or awaiting: raise RuntimeError("finished early")
                    disarming = True
                else:
                    raise RuntimeError("unexpected stage")
        raise RuntimeError("capture incomplete; device state unknown, do not retry this boot")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path); p.add_argument("probe_sha256")
    p.add_argument("--supervisor-sha256", required=True); p.add_argument("--wrapper-sha256", required=True)
    p.add_argument("--timeout", type=float, default=35); a = p.parse_args()
    if not 1 <= a.timeout <= 300: p.error("timeout must be between 1 and 300 seconds")
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            result = capture(sock, a.log, a.probe_sha256, a.timeout, a.supervisor_sha256, a.wrapper_sha256)
    except (OSError, RuntimeError, ValueError) as e:
        p.exit(1, f"capture failed: {e}; do not retry this boot\n")
    print(f"captured one GPU revision read: 0x{result['gpu-revision']:08x}; {a.log}")


if __name__ == "__main__":
    main()
