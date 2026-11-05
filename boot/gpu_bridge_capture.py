#!/usr/bin/env python3
"""Checkpoint experimental bridge writes; offline validation is not hardware safety."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import struct
import time

TABLE_SHA = "b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4"
PLAN_SHA = "1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435"
BRIDGE_WRAPPER_SHA = "30a970eab8db5382734850adb65543f7b9cd3aee8f007469a2e3cfbfa8729317"
SIM_WRAPPER_SHA = "3eae753d93113b09c1988e97fa6fae9ba1a1c67d007876e597b9d5324e07662c"
PMGR_BEFORE = b"stage=before-pmgr-read address=0x20e020320 width=32"
PMGR_AFTER = b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0"


def plan_steps(data):
    if len(data) != 528 or hashlib.sha256(data).hexdigest() != PLAN_SHA:
        raise ValueError("bridge plan checksum or length mismatch")
    if any(hashlib.sha256(data[i:i+264]).hexdigest() != TABLE_SHA for i in (0,264)):
        raise ValueError("bridge table checksum mismatch")
    steps = [("gpc-state", 0x201e01000, "read", 0)]
    for t, base in enumerate((0x201f00000,0x201f80000)):
        for i, (offset, value) in enumerate(struct.iter_unpack("<II", data[t*264:(t+1)*264])):
            if offset != (0x40000+(i-1)*4 if i else 0x18):
                raise ValueError("unexpected bridge offset")
            steps.append((f"bridge-{t+9}-{i:02d}",base+offset,"write",value))
    return steps


def capture(sock, path, binary_hash, data, timeout, supervised=False, supervisor_hash=None, simulate_bridge=False):
    if not re.fullmatch(r"[0-9a-f]{64}", binary_hash):
        raise ValueError("invalid binary hash")
    if simulate_bridge and not supervised:
        raise ValueError("simulation requires supervisor")
    if supervised and (not supervisor_hash or not re.fullmatch(r"[0-9a-f]{64}", supervisor_hash)):
        raise ValueError("invalid supervisor hash")
    steps = plan_steps(data)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    deadline = time.monotonic() + timeout
    stage, buffer, watchdog_stage, feed_count = 0, b"", 0, 0
    with os.fdopen(fd, "wb") as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        command = (f"test \"$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d ' ' -f 1)\" = {supervisor_hash} && "
                   f"/tmp/gpu-watchdog-supervisor {'--simulate-bridge' if simulate_bridge else '--bridge'} {binary_hash}"
                   if supervised else f"/tmp/gpu-bridge-once-run {binary_hash}")
        if supervised:
            wrapper = '/tmp/gpu-bridge-sim-live-run' if simulate_bridge else '/tmp/gpu-bridge-once-run'
            wrapper_hash = SIM_WRAPPER_SHA if simulate_bridge else BRIDGE_WRAPPER_SHA
            command = (f"test \"$(sha256sum {wrapper} | cut -d ' ' -f 1)\" = {wrapper_hash} && " + command)
        sock.sendall((command + "\n").encode())
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno())
            buffer += chunk
            if len(buffer) > 65536: raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n",1)
                line = line.strip(b"\r")
                if not line.startswith(b"stage="): continue
                log.write(b"\nhost-stage time_ns="+str(time.time_ns()).encode()+b" "+line+b"\n")
                log.flush(); os.fsync(log.fileno())
                if supervised and watchdog_stage < 2:
                    if watchdog_stage == 0 and line == b"stage=before-watchdog-open":
                        if b"stage=" in buffer: raise RuntimeError("pipelined watchdog checkpoint")
                        sock.sendall(b"ARM\n"); watchdog_stage = 1; continue
                    if watchdog_stage == 1 and line == b"stage=watchdog-armed timeout=20":
                        watchdog_stage = 2; continue
                    raise RuntimeError("unexpected watchdog checkpoint")
                if supervised and watchdog_stage == 3:
                    if line != b"stage=watchdog-disarmed": raise RuntimeError("watchdog not disarmed")
                    return
                if stage == 0:
                    if line != PMGR_BEFORE or b"stage=" in buffer: raise RuntimeError("unexpected PMGR checkpoint")
                    sock.sendall(b"READ\n");stage=1;continue
                if stage == 1:
                    if line != PMGR_AFTER: raise RuntimeError("unexpected PMGR state")
                    stage=2
                    if supervised:
                        feed_count += 1; sock.sendall(f"FEED {feed_count}\n".encode())
                    continue
                index = (stage-2)//2
                if index == len(steps):
                    if line != b"stage=finished rc=0": raise RuntimeError("missing successful completion")
                    if supervised:
                        watchdog_stage = 3; continue
                    return
                name,address,operation,value = steps[index]
                if stage%2 == 0:
                    expected=f"stage=before-{name} address=0x{address:x} op={operation} value=0x{value:08x}".encode()
                    if line != expected or b"stage=" in buffer: raise RuntimeError("unexpected or pipelined checkpoint")
                    sock.sendall(b"ACCESS\n")
                else:
                    expected=f"stage=after-{name} value=0x{value:08x}".encode()
                    if line != expected: raise RuntimeError("unexpected access result")
                    if supervised:
                        feed_count += 1; sock.sendall(f"FEED {feed_count}\n".encode())
                stage+=1
    raise RuntimeError("capture incomplete; hardware state is unknown")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("log",type=Path);p.add_argument("binary_sha256");p.add_argument("plan",type=Path)
    p.add_argument("--timeout",type=float,default=60);p.add_argument("--supervised",action="store_true");p.add_argument("--supervisor-sha256");p.add_argument("--simulate-bridge",action="store_true");args=p.parse_args()
    if not 1 <= args.timeout <= 300:p.error("timeout must be between 1 and 300 seconds")
    try:
        data=args.plan.read_bytes()
        with socket.create_connection(("172.16.42.1",23),timeout=5) as sock:
            capture(sock,args.log,args.binary_sha256,data,args.timeout,args.supervised,args.supervisor_sha256,args.simulate_bridge)
    except (OSError, RuntimeError, ValueError) as error:
        p.exit(1,f"capture failed: {error}; do not retry this boot\n")
    label = "Simulated bridge protocol" if args.simulate_bridge else "Bridge write sequence"
    print(f"{label} reported complete: {args.log}")


if __name__ == "__main__": main()
