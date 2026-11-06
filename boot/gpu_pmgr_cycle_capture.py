#!/usr/bin/env python3
"""Capture one acknowledged PMGR off/on generation."""
import argparse, os, re, socket, time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")

def capture(sock, path, module_hash, notes_hash, timeout):
    if not HEX.fullmatch(module_hash) or not HEX.fullmatch(notes_hash):
        raise ValueError("invalid SHA-256")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        sock.sendall(f"/tmp/gpu-pmgr-cycle-run {module_hash} {notes_hash}\n".encode())
        buffer = b""
        deadline = time.monotonic() + timeout
        stage = 0
        while time.monotonic() < deadline:
            sock.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except socket.timeout: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); buffer += chunk
            if len(buffer) > 65536: raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip(b"\r")
                if not line.startswith(b"stage="): continue
                if stage == 0:
                    if not line.startswith(b"stage=before-pmgr-read "):
                        raise RuntimeError("missing PMGR baseline")
                    sock.sendall(b"READ\n"); stage = 1
                elif stage == 1:
                    if line != b"stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0":
                        raise RuntimeError("unexpected PMGR baseline")
                    stage = 2
                elif stage == 2:
                    expected = f"stage=before-pmgr-cycle module={module_hash} kernel_notes={notes_hash}".encode()
                    if line != expected: raise RuntimeError("missing cycle checkpoint")
                    sock.sendall(b"CYCLE\n"); stage = 3
                elif stage == 3:
                    if line != b"stage=after-pmgr-cycle rc=0":
                        raise RuntimeError("cycle failed; do not retry this boot")
                    return
        raise RuntimeError("capture incomplete; device state is unknown")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("log", type=Path); p.add_argument("module_sha256"); p.add_argument("kernel_notes_sha256")
    p.add_argument("--timeout", type=float, default=40); a = p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
            capture(sock, a.log, a.module_sha256, a.kernel_notes_sha256, a.timeout)
    except (OSError, RuntimeError, ValueError) as error:
        p.exit(1, f"capture failed: {error}; do not retry this boot\n")
    print(f"captured PMGR cycle: {a.log}")

if __name__ == "__main__": main()
