#!/usr/bin/env python3
"""Capture one post-cycle Fender wake attempt; never issues RGX access."""
import argparse, os, re, socket, time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
FIXED = (("initial-state", 0x1000, "read", 0), ("reset", 0x20000, "write", 0),
         ("reset-state", 0x1000, "write", 0x10), ("hold", 0x20000, "write", 0x20),
         ("hold-confirm", 0x20000, "read", 0), ("setup-mask", 0x10000, "write", 0xffff0000),
         ("setup-control", 0, "write", 0x40000000), ("request-state", 0x1000, "write", 0x11))

def capture(sock, path, binary_hash, timeout):
    if not HEX.fullmatch(binary_hash): raise ValueError("invalid binary SHA-256")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log:
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        sock.sendall(f"/tmp/gpu-fender-wake-run {binary_hash}\n".encode())
        buf, step, poll_kind, poll_count = b"", 0, None, 0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except socket.timeout: continue
            if not chunk: break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); buf += chunk
            if len(buf) > 65536: raise RuntimeError("capture exceeded 64 KiB")
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1); line = line.strip(b"\r")
                if not line.startswith(b"stage="): continue
                if poll_kind:
                    prefix = f"stage=before-{poll_kind}-".encode()
                    if line.startswith(prefix):
                        sock.sendall(b"ACCESS\n"); continue
                    prefix = f"stage=after-{poll_kind}-".encode()
                    if line.startswith(prefix):
                        value = int(line.rsplit(b"=", 1)[1], 16)
                        done = value == 0 if poll_kind == "reset-zero" else not value & 0x10
                        if done:
                            poll_kind = None
                            poll_count = 0
                        elif poll_count >= 63: raise RuntimeError("Fender poll limit reached")
                        else: poll_count += 1
                        continue
                    raise RuntimeError("unexpected Fender poll output")
                if step < len(FIXED) * 2:
                    name, offset, op, expected = FIXED[step // 2]
                    before = f"stage=before-{name} address=0x{0x201e00000 + offset:x} op={op} value=0x{expected:08x}".encode()
                    if step % 2 == 0:
                        if line != before: raise RuntimeError("unexpected Fender checkpoint")
                        sock.sendall(b"ACCESS\n"); step += 1; continue
                    match = re.fullmatch(rb"stage=after-" + name.encode() + rb" value=0x([0-9a-f]{8})", line)
                    actual = int(match.group(1), 16) if match else None
                    if actual != (0x20 if name == "hold-confirm" else expected): raise RuntimeError("Fender checkpoint mismatch")
                    step += 1
                    if name == "reset": poll_kind = "reset-clear"
                    elif name == "reset-state": poll_kind = "reset-zero"
                    elif name == "request-state": poll_kind = "wake"
                    continue
                if line == b"stage=finished rc=0": return
                if line == b"stage=finished rc=1": raise RuntimeError("Fender sequence failed; do not retry")
                raise RuntimeError("unexpected Fender output")
        raise RuntimeError("capture incomplete; device state is unknown")

def main():
    p = argparse.ArgumentParser(); p.add_argument("log", type=Path); p.add_argument("binary_sha256"); p.add_argument("--timeout", type=float, default=40); a = p.parse_args()
    try:
        with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock: capture(sock, a.log, a.binary_sha256, a.timeout)
    except (OSError, RuntimeError, ValueError) as e: p.exit(1, f"capture failed: {e}; do not retry this boot\n")
    print(f"captured Fender wake: {a.log}")
if __name__ == "__main__": main()
