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

def capture(sock, path, probe_hash, timeout):
    if not HEX.fullmatch(probe_hash): raise ValueError("invalid probe hash")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(parent)
        finally: os.close(parent)
        sock.sendall(f"/tmp/gpu-bridge-postgpc-cycle-run {probe_hash}\n".encode())
        buf=b""; stage=0; deadline=time.monotonic()+timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001,min(1.0,deadline-time.monotonic())))
            try: chunk=sock.recv(4096)
            except socket.timeout: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); buf += chunk
            if len(buf)>65536: raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buf:
                line,buf=buf.split(b"\n",1); line=line.strip(b"\r")
                if line.startswith(b"stage=before-"):
                    if stage >= len(STAGES) or line != STAGES[stage]: raise RuntimeError("unexpected checkpoint")
                    sock.sendall(b"READ\n"); stage += 1
                elif line.startswith(b"stage=after-"):
                    if stage == 1 and line != b"stage=after-pmgr-read raw=0x000003ff": raise RuntimeError("unexpected PMGR state")
                    if stage == 2 and line != b"stage=after-gpc-state raw=0x00000001": raise RuntimeError("unexpected GPC state")
                    if stage == 3 and line != b"stage=after-gpc-control raw=0x40000000": raise RuntimeError("unexpected GPC control")
                    if stage in (4,5) and not re.fullmatch(rb"stage=after-bridge-(?:18|1c) raw=0x[0-9a-f]{8}", line): raise RuntimeError("unexpected bridge result")
                elif line == b"stage=finished rc=0":
                    if stage != len(STAGES): raise RuntimeError("finished early")
                    return
        raise RuntimeError("capture incomplete; do not retry this boot")

def main():
    p=argparse.ArgumentParser(); p.add_argument("log",type=Path); p.add_argument("probe_sha256"); p.add_argument("--timeout",type=float,default=30); a=p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1",23),timeout=5) as s: capture(s,a.log,a.probe_sha256,a.timeout)
    except (OSError,RuntimeError,ValueError) as e: p.exit(1,f"capture failed: {e}\n")
    print(f"captured post-GPC bridge readback: {a.log}")
if __name__ == "__main__": main()
