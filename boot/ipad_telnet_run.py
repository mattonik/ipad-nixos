#!/usr/bin/env python3
"""Run one shell command on the iPad's telnet recovery shell (172.16.42.1:23) and print its output.

The recovery shell is busybox telnetd with `-l /telnet_connect.sh` (no login). The command is wrapped between two random markers so the
output can be cut out of the telnet stream (IAC option negotiation and the prompt are stripped). Exit status is that of the command.

  boot/ipad_telnet_run.py [--timeout S] 'command ...'
"""
import argparse
import re
import secrets
import socket
import subprocess
from pathlib import Path
import sys
import time


SSH_KEY = Path(__file__).resolve().parent.parent / "artifacts/live/ssh/ipad_ed25519"


def run_ssh(command, timeout=60, host="172.16.42.1"):
    """NixOS-in-RAM has no telnet recovery shell: run the command over ssh with the dedicated key (the RAM root makes a new host key each boot, so the host key is not pinned on this direct USB link)."""
    r = subprocess.run(["ssh", "-i", str(SSH_KEY), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR", f"root@{host}", command],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip("\n"), r.returncode


def run(command, timeout=60, host="172.16.42.1", port=23):
    """Telnet recovery shell if it answers (stage 1 / postmarketOS), otherwise ssh (NixOS)."""
    try:
        socket.create_connection((host, port), timeout=3).close()
    except OSError:
        return run_ssh(command, timeout, host)
    return run_telnet(command, timeout, host, port)


def run_telnet(command, timeout=60, host="172.16.42.1", port=23):
    mark = secrets.token_hex(6)
    start, end = f"@@S{mark}@@", f"@@E{mark}@@"
    s = socket.create_connection((host, port), timeout=10)
    s.settimeout(1.0)
    time.sleep(0.5)
    payload = f"echo {start}; ( {command} ) 2>&1; echo {end}$?\n"
    s.sendall(payload.encode())
    buf = b""
    deadline = time.time() + timeout
    pat = re.compile(re.escape(end).encode() + rb"(\d+)")
    while time.time() < deadline:
        try:
            chunk = s.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        if pat.search(buf.split(start.encode(), 2)[-1]) and buf.count(start.encode()) >= 2:
            break
    s.close()
    text = re.sub(rb"\xff[\xfb-\xfe].|\xff.", b"", buf)
    parts = text.split(start.encode())
    body = parts[-1] if len(parts) >= 3 else b""
    m = pat.search(body)
    rc = int(m.group(1)) if m else 255
    out = body[:m.start()] if m else body
    out = re.sub(rb"\x1b\[[0-9;]*m", b"", out.replace(b"\r", b"")).decode("utf-8", "replace").strip("\n")
    return out, rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command")
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()
    out, rc = run(a.command, a.timeout)
    print(out)
    sys.exit(rc)


if __name__ == "__main__":
    main()
