#!/usr/bin/env python3
import argparse, os, re, socket, time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
STAGES = (
    b"stage=before-pmgr-read address=0x20e020320 width=32",
    b"stage=before-gpc-state address=0x201e01000 width=32",
    b"stage=before-gpc-control address=0x201e00000 width=32",
    b"stage=before-bridge-18 address=0x201f00018 width=32",
    b"stage=before-bridge-1c address=0x201f0001c width=32",
)

def capture(sock, path, probe_hash, timeout, supervised=False, supervisor_hash=None, wrapper_hash=None):
    if not HEX.fullmatch(probe_hash): raise ValueError("invalid probe hash")
    if supervised and any(not value or not HEX.fullmatch(value) for value in (supervisor_hash, wrapper_hash)):
        raise ValueError("invalid supervisor or wrapper hash")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(parent)
        finally: os.close(parent)
        if supervised:
            command = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor|cut -d " " -f1)" = {supervisor_hash} && '
                       f'test "$(sha256sum /tmp/gpu-bridge-postgpc-cycle-run|cut -d " " -f1)" = {wrapper_hash} && '
                       f"/tmp/gpu-watchdog-supervisor --postgpc-cycle {probe_hash}\n")
        else:
            command = f"/tmp/gpu-bridge-postgpc-cycle-run {probe_hash}\n"
        sock.sendall(command.encode())
        buf=b""; stage=0; watchdog=0; feeds=0; values={}; echoes=set(); awaiting_after=False; awaiting_disarm=False; started=False; deadline=time.monotonic()+timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001,min(1.0,deadline-time.monotonic())))
            try: chunk=sock.recv(4096)
            except socket.timeout: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); buf += chunk
            if len(buf)>65536: raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buf:
                line,buf=buf.split(b"\n",1); line=line.strip(b"\r")
                if not started:
                    if not line.startswith(b"stage="): continue
                    started=True
                if line in echoes:
                    echoes.remove(line); continue
                if supervised and watchdog < 2:
                    if watchdog == 0 and line == b"stage=before-watchdog-open":
                        echoes.add(b"ARM"); sock.sendall(b"ARM\n"); watchdog=1; continue
                    if watchdog == 1 and line == b"stage=watchdog-armed timeout=20":
                        watchdog=2; continue
                    raise RuntimeError("unexpected watchdog checkpoint")
                if supervised and awaiting_disarm:
                    if line != b"stage=watchdog-disarmed": raise RuntimeError("watchdog not disarmed")
                    return values
                if line.startswith(b"stage=before-"):
                    if awaiting_after or stage >= len(STAGES) or line != STAGES[stage]: raise RuntimeError("unexpected checkpoint")
                    echoes.add(b"READ"); sock.sendall(b"READ\n"); stage += 1; awaiting_after=True
                elif line.startswith(b"stage=after-"):
                    if not awaiting_after: raise RuntimeError("unexpected checkpoint")
                    if stage == 1 and not line.startswith(b"stage=after-pmgr-read raw=0x000003ff "): raise RuntimeError("unexpected PMGR state")
                    if supervised and stage == 1:
                        feeds += 1; echo=f"FEED {feeds}".encode(); echoes.add(echo); sock.sendall(echo+b"\n")
                    if stage == 2 and line != b"stage=after-gpc-state raw=0x00000001": raise RuntimeError("unexpected GPC state")
                    if stage == 3 and line != b"stage=after-gpc-control raw=0x40000000": raise RuntimeError("unexpected GPC control")
                    if stage in (4,5):
                        match = re.fullmatch(rb"stage=after-(bridge-(?:18|1c)) raw=0x([0-9a-f]{8})", line)
                        if not match: raise RuntimeError("unexpected bridge result")
                        values[match.group(1).decode()] = int(match.group(2), 16)
                    if supervised and stage in (2,3,4,5):
                        feeds += 1; echo=f"FEED {feeds}".encode(); echoes.add(echo); sock.sendall(echo+b"\n")
                    awaiting_after=False
                elif line == b"stage=finished rc=0":
                    if stage != len(STAGES) or awaiting_after: raise RuntimeError("finished early")
                    if supervised: awaiting_disarm=True; continue
                    return values
        raise RuntimeError("capture incomplete; do not retry this boot")

def main():
    p=argparse.ArgumentParser(); p.add_argument("log",type=Path); p.add_argument("probe_sha256"); p.add_argument("--timeout",type=float,default=30)
    p.add_argument("--supervised",action="store_true"); p.add_argument("--supervisor-sha256"); p.add_argument("--wrapper-sha256"); a=p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1",23),timeout=5) as s: values = capture(s,a.log,a.probe_sha256,a.timeout,a.supervised,a.supervisor_sha256,a.wrapper_sha256)
    except (OSError,RuntimeError,ValueError) as e: p.exit(1,f"capture failed: {e}\n")
    print(f"captured post-GPC bridge readback: {a.log}; +0x18=0x{values['bridge-18']:08x} (baseline 0x00000004), +0x1c=0x{values['bridge-1c']:08x} (baseline 0x00010001)")
if __name__ == "__main__": main()
