#!/usr/bin/env python3
"""Capture one watchdog-supervised GPC setup and immediate page-5 sample."""
import argparse
import os
import re
import socket
import time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
BEFORE = (
    b"stage=before-pmgr-read address=0x20e020320 width=32",
    b"stage=before-gpc-state address=0x201e01000 width=32",
    b"stage=before-gpc-page5 address=0x20e005004 width=32",
)
CHECKPOINTS = (b"checkpoint=before-gpc-writes", b"checkpoint=before-gpc-poll", b"checkpoint=before-page5-read")


def capture(sock, path, probe_hash, supervisor_hash, wrapper_hash, boot_id, timeout=40):
    if not all(HEX.fullmatch(v or "") for v in (probe_hash, supervisor_hash, wrapper_hash)):
        raise ValueError("invalid hash")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", boot_id):
        raise ValueError("invalid boot ID")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb', buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(parent)
        finally: os.close(parent)
        command = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor_hash} && '
                   f'test "$(sha256sum /tmp/gpu-gpc-page5-timed-run | cut -d " " -f 1)" = {wrapper_hash} && '
                   f'/tmp/gpu-watchdog-supervisor --gpc-page5-timed {probe_hash} {boot_id}\n')
        sock.sendall(command.encode())
        buf = b''; stage = watchdog = feeds = cp = 0
        awaiting = disarming = poll_ok = duration_ok = False
        result = None; echoes = set(); deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            log.write(chunk); os.fsync(log.fileno()); buf += chunk
            if len(buf) > 65536: raise RuntimeError('capture exceeded 64 KiB')
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1); line = line.strip(b'\r')
                if line in echoes: echoes.remove(line); continue
                if line.startswith(b'checkpoint='):
                    if stage != 2 or not awaiting: raise RuntimeError('unexpected checkpoint')
                    if cp < 3:
                        if line != CHECKPOINTS[cp]: raise RuntimeError('unexpected batch checkpoint')
                        cp += 1; continue
                    match = re.fullmatch(rb'checkpoint=gpc-poll-ok raw=0x([0-9a-f]{8}) polls=([0-9]+)', line)
                    if cp == 3 and match and int(match[1], 16) & 0x1f == 1 and 1 <= int(match[2]) <= 1000:
                        cp = 4; poll_ok = True; continue
                    match = re.fullmatch(rb'checkpoint=poll-to-sysfs-return-ns value=([0-9]+)', line)
                    if cp == 4 and match:
                        cp = 5; duration_ok = True; continue
                    raise RuntimeError('invalid batch checkpoint')
                if not line.startswith(b'stage='): continue
                if watchdog == 0:
                    if line != b'stage=before-watchdog-open': raise RuntimeError('missing watchdog arm checkpoint')
                    echoes.add(b'ARM'); sock.sendall(b'ARM\n'); watchdog = 1; continue
                if watchdog == 1:
                    if line != b'stage=watchdog-armed timeout=20': raise RuntimeError('watchdog did not arm')
                    watchdog = 2; continue
                if disarming:
                    if line != b'stage=watchdog-disarmed' or b'stage=' in buf: raise RuntimeError('watchdog not disarmed')
                    return result
                if line.startswith(b'stage=before-'):
                    if awaiting or stage >= len(BEFORE) or line != BEFORE[stage] or b'stage=' in buf: raise RuntimeError('unexpected or pipelined checkpoint')
                    echoes.add(b'READ'); sock.sendall(b'READ\n'); awaiting = True; continue
                if line.startswith(b'stage=after-'):
                    if not awaiting or b'stage=' in buf: raise RuntimeError('unexpected or pipelined result')
                    if stage == 0 and line != b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0': raise RuntimeError('PMGR not active')
                    if stage == 1 and line != b'stage=after-gpc-state raw=0x00000000': raise RuntimeError('GPC not initially zero')
                    if stage == 2:
                        match = re.fullmatch(rb'stage=after-gpc-page5 address=0x20e005004 value=0x([0-9a-f]{8})', line)
                        if not match or not poll_ok or not duration_ok or cp != 5: raise RuntimeError('invalid batch result')
                        result = int(match[1], 16)
                    stage += 1; awaiting = False; feeds += 1
                    echo = f'FEED {feeds}'.encode(); echoes.add(echo); sock.sendall(echo + b'\n'); continue
                if line == b'stage=finished rc=0' and stage == len(BEFORE) and not awaiting:
                    disarming = True; continue
                raise RuntimeError('unexpected stage')
    raise RuntimeError('capture incomplete; device state unknown, do not retry this boot')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path); p.add_argument('probe_sha256'); p.add_argument('boot_id'); p.add_argument('--supervisor-sha256', required=True); p.add_argument('--wrapper-sha256', required=True); p.add_argument('--timeout', type=int, default=40)
    a = p.parse_args()
    if not 1 <= a.timeout <= 300: p.error('timeout must be between 1 and 300 seconds')
    try:
        with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
            value = capture(sock, a.log, a.probe_sha256, a.supervisor_sha256, a.wrapper_sha256, a.boot_id, a.timeout)
    except (OSError, RuntimeError, ValueError) as e:
        p.exit(1, f'capture failed: {e}; do not retry this boot\n')
    print(f'captured post-poll page-5 value: 0x{value:08x}; {a.log}')
if __name__ == '__main__': main()
