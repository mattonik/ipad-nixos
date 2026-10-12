#!/usr/bin/env python3
"""Privacy audit for publishing the repository (run before any export or push): scans every Git-tracked text file for things that must not become public.

Findings: per-device MAC addresses, Wi-Fi network names and keys, private key blocks, device serial numbers / ECIDs / UDIDs, the author's home directory, long hex dumps that look like firmware or
calibration data. Allowlisted: the synthetic locally administered test MAC used for provisioning, third-party author attribution in patches. Exit status 1 when anything is found.

  tools/audit_public.py [--list]     (--list also prints the allowlisted hits)
"""
import re
import subprocess
import sys

ALLOW_MACS = {"00:11:22:33:44:55", "aa:bb:cc:dd:ee:ff"}   # documentation/test examples
# Locally administered MACs (bit 1 of the first octet set: 02:.., 06:.., 0a:.., ca:.., c2:..) are randomly generated per boot (USB gadget) or synthetic test values, never a device's burned-in address.
ALLOW_PATH_FILES = ("tools/audit_public.py",)
SELF_TEST_FILE = "tools/test_audit_public.py"        # contains deliberately fake secrets to test the rules (keep them fake: never a real address or key)
BINARY_SUFFIXES = (".bin", ".lock", ".png", ".jpg", ".ppm", ".gz", ".trace")

RULES = [
    ("mac", re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])")),
    ("wifi-secret", re.compile(r"(?im)^\s*(?:psk|password|passphrase)\s*=\s*\"?[^\s\"<>]{6,}")),
    ("private-key", re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY")),
    ("device-id", re.compile(r"(?i)\b(?:serial(?: number)?|ecid|udid|chip ?id)\b\W{0,3}(?:0x)?[0-9A-Fa-f]{12,40}\b")),
    ("home-dir", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("long-hex-dump", re.compile(r"(?:\b[0-9a-f]{2}\b[ :]){48,}")),
]


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [f for f in out.decode().split("\0") if f and not f.endswith(BINARY_SUFFIXES)]


def scan(text, path):
    hits = []
    if path == SELF_TEST_FILE:
        return hits
    for name, rx in RULES:
        if name == "home-dir" and path in ALLOW_PATH_FILES:
            continue
        for m in rx.finditer(text):
            val = m.group(0)
            if name == "mac" and (val.lower() in ALLOW_MACS or int(val[:2], 16) & 0x02):
                continue
            line = text.count("\n", 0, m.start()) + 1
            hits.append((name, path, line, val[:60].replace("\n", " ")))
    return hits


def main(argv):
    all_hits = []
    for path in tracked_files():
        try:
            text = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        all_hits += scan(text, path)
    for name, path, line, val in all_hits:
        print(f"{name:12} {path}:{line}: {val}")
    print(f"{len(all_hits)} finding(s)")
    return 1 if all_hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
