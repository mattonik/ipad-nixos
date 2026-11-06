#!/usr/bin/env python3
"""Capture read-only J81 Fender status over the diagnostic shell."""
import argparse, os, re, socket, time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")

def capture(sock, path, module_hash, timeout):
    if not HEX.fullmatch(module_hash): raise ValueError("invalid module SHA-256")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        sock.sendall(f"/tmp/gpu-fender-status-run {module_hash}\n".encode())
        buf = b""; seen = set(); deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except socket.timeout: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); buf += chunk
            if len(buf) > 16384: raise RuntimeError("capture exceeded 16 KiB")
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1); line = line.strip(b"\r")
                if line.startswith(b"stage=before-fender-status "):
                    if line != f"stage=before-fender-status module={module_hash}".encode(): raise RuntimeError("module checkpoint mismatch")
                    seen.add("before")
                elif line.startswith((b"stage=state value=", b"stage=control value=", b"stage=hold value=")):
                    if not re.fullmatch(rb"stage=(state|control|hold) value=0x[0-9a-f]{8}", line): raise RuntimeError("invalid status value")
                    seen.add(line.split(b"=", 1)[0].decode())
                elif line == b"stage=finished rc=0":
                    if seen != {"before", "stage"}: raise RuntimeError("incomplete status capture")
                    return
                elif line.startswith(b"stage=finished rc="): raise RuntimeError("status probe failed")
        raise RuntimeError("capture incomplete; do not retry this boot")

def main():
    p = argparse.ArgumentParser(); p.add_argument("log", type=Path); p.add_argument("module_sha256"); p.add_argument("--timeout", type=float, default=20); a = p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock: capture(sock, a.log, a.module_sha256, a.timeout)
    except (OSError, RuntimeError, ValueError) as e: p.exit(1, f"capture failed: {e}\n")
    print(f"captured Fender status: {a.log}")
if __name__ == "__main__": main()
