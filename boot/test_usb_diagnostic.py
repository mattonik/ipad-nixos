#!/usr/bin/env python3
"""Check the built payload without USB hardware (stdlib only).

Usage: python3 boot/test_usb_diagnostic.py result-m1n1-control result-usb-diagnostic
"""
import gzip
import hashlib
from pathlib import Path
import subprocess
import sys


def entries(data):
    """Read concatenated newc archives, including entries after TRAILER!!!."""
    result = {}
    offset = 0
    while offset < len(data):
        if data[offset] == 0:
            offset += 1
            continue
        assert data[offset:offset + 6] == b"070701", offset
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16)
                  for i in range(13)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        start = offset + 110
        name = data[start:start + namesize - 1].decode().removeprefix("./")
        start = (start + namesize + 3) & ~3
        assert start + size <= len(data)
        if name != "TRAILER!!!":
            result[name] = (mode, fields[9:11], data[start:start + size])
        offset = (start + size + 3) & ~3
    return result


control, diagnostic = map(Path, sys.argv[1:3])
script = Path(__file__).with_name("usb-diagnostic.sh")
subprocess.run(["sh", "-n", str(script)], check=True)
for name in ("Pongo.bin", "m1n1.bin", "t7001-j81.dtb", "Image.gz"):
    assert (diagnostic / name).read_bytes() == (control / name).read_bytes(), name

original = gzip.decompress((control / "initramfs.gz").read_bytes())
modified = gzip.decompress((diagnostic / "initramfs.gz").read_bytes())
assert modified.startswith(original), "original archive must remain byte-identical"
before, after = entries(original), entries(modified)
hook = "etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh"
assert set(entries(modified[len(original):])) == {hook}, "overlay changes only debug hook"
assert set(before) == set(after)
assert {name for name in before if before[name] != after[name]} == {hook}
assert after[hook][0] & 0o777 == 0o755
assert after[hook][2] == script.read_bytes()

bootargs = (diagnostic / "bootargs").read_bytes()
assert bootargs.startswith(b"chosen.bootargs=") and bootargs.endswith(b"\n")
assert b"ignore_loglevel" not in bootargs
assert b"pd_ignore_unused clk_ignore_unused" in bootargs
assert b'func ecm_set_alt +p' in bootargs
parts = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
assert (diagnostic / "m1n1-linux.bin").read_bytes() == b"".join(
    (diagnostic / name).read_bytes() for name in parts)
for line in (diagnostic / "SHA256SUMS").read_text().splitlines():
    digest, path = line.split()
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
print("USB diagnostic check passed: original boot components intact; executable hook overlaid")
