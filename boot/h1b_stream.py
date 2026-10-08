#!/usr/bin/env python3
"""Stream the kernel log of a booting H1B payload to the host, until the iPad stops answering.

Usage: python3 boot/h1b_stream.py PRIVATE_PAYLOAD_DIR [--wait SECONDS]

For payloads whose Wi-Fi path resets the machine (run 15/16): boot with brcmfmac.h1b_defer_s=N (N larger than the time the
USB network needs, about 45), start this tool right after the loader finishes. It waits for 172.16.42.1, connects to the debug
shell and repeatedly reads `dmesg` (read-only), writing every new line to PRIVATE_PAYLOAD_DIR/stream-<UTC>.log (0600) as it arrives,
so the last lines before a reset are on the host. Nothing is written to the device.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def new_lines(previous, current):
    """Lines of `current` that were not in `previous` (dmesg only grows; compare by length of the common prefix)."""
    if current.startswith(previous):
        return current[len(previous):]
    return current  # the ring buffer wrapped or was cleared: take everything


def stream(shell, out_path, deadline_s=600, interval=0.3, clock=time.monotonic, sleep=time.sleep):
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    previous, end = "", clock() + deadline_s
    with os.fdopen(fd, "w") as f:
        while clock() < end:
            try:
                text = shell.run("dmesg", timeout=15, check=False)
            except (OSError, ConnectionError) as e:
                f.write(f"\n# link lost: {type(e).__name__}\n")
                break
            fresh = new_lines(previous, text)
            if fresh:
                f.write(fresh)
                f.flush()
                os.fsync(f.fileno())
                previous = text
            sleep(interval)
    return previous


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("payload_dir")
    ap.add_argument("--wait", type=float, default=180)
    args = ap.parse_args(argv[1:])
    t0 = time.monotonic()
    while subprocess.call(["ping", "-c1", "-t1", "172.16.42.1"], stdout=subprocess.DEVNULL) != 0:
        if time.monotonic() - t0 > args.wait:
            print("iPad did not answer at 172.16.42.1")
            return 1
        time.sleep(1)
    print(f"iPad answered after {time.monotonic() - t0:.0f} s; streaming")
    from ipad_console import IPadShell
    from session_evidence import SessionEvidence
    payload = Path(args.payload_dir)
    shell = IPadShell(evidence=SessionEvidence([f"payload={payload / 'm1n1-linux.bin'}"]))
    shell.connect()
    out = payload / ("stream-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".log")
    last = stream(shell, out)
    print("stream ended; log:", out, f"({len(last.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
