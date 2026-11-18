#!/usr/bin/env python3
"""Capture one watchdog-supervised J81 post-GPC Fender status snapshot."""
import argparse, os, re, socket, time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
RESULT = re.compile(rb"stage=after-gpc-fender control=0x[0-9a-f]{8} settle=0x[0-9a-f]{8} state=0x[0-9a-f]{8} hold=0x[0-9a-f]{8} page5=0x[0-9a-f]{8}")

def capture(sock, path, probe, supervisor, runner, boot_id, timeout):
    if not all(HEX.fullmatch(x or "") for x in (probe, supervisor, runner)):
        raise ValueError("invalid SHA-256")
    if not re.fullmatch(r"[0-9a-f-]{36}", boot_id): raise ValueError("invalid boot ID")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        cmd = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f1)" = {supervisor} && '
               f'test "$(sha256sum /tmp/gpu-gpc-fender-status-run | cut -d " " -f1)" = {runner} && '
               f'/tmp/gpu-watchdog-supervisor --gpc-fender-status {probe} {boot_id}\n')
        sock.sendall(cmd.encode()); buf = b""; deadline = time.monotonic() + timeout
        armed = stages = 0; result = None
        while time.monotonic() < deadline:
            sock.settimeout(min(1, max(.01, deadline-time.monotonic())))
            try: chunk = sock.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            log.write(chunk); buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1); line = line.strip(b"\r")
                if line == b"stage=before-watchdog-open" and not armed:
                    sock.sendall(b"ARM\n"); armed = 1
                elif line == b"stage=watchdog-armed timeout=20" and armed == 1:
                    armed = 2
                elif line.startswith(b"stage=before-gpc-") and armed == 2:
                    sock.sendall(b"READ\n")
                elif line.startswith(b"stage=after-gpc-state raw=0x00000000") and stages == 0:
                    stages = 1; sock.sendall(b"FEED 1\n")
                elif RESULT.fullmatch(line) and stages == 1:
                    result = line.decode(); stages = 2; sock.sendall(b"FEED 2\n")
                elif line == b"stage=watchdog-disarmed" and stages == 2:
                    return result
                elif line.startswith(b"stage=finished rc=") and line != b"stage=finished rc=0":
                    raise RuntimeError("probe failed")
        raise RuntimeError("capture incomplete; do not retry this boot")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path); p.add_argument("probe_sha256"); p.add_argument("boot_id")
    p.add_argument("--supervisor-sha256", required=True); p.add_argument("--runner-sha256", required=True); p.add_argument("--timeout", type=int, default=40)
    a=p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1",23), timeout=5) as sock:
            value=capture(sock,a.log,a.probe_sha256,a.supervisor_sha256,a.runner_sha256,a.boot_id,a.timeout)
    except (OSError,RuntimeError,ValueError) as e: p.exit(1,f"capture failed: {e}\n")
    print(f"captured post-GPC Fender status: {value}; {a.log}")
if __name__ == "__main__": main()
