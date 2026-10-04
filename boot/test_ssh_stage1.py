#!/usr/bin/env python3
"""Static gate for the SSH stage 1 payload (stdlib only, no hardware).

Usage: python3 boot/test_ssh_stage1.py result-control result-ssh-stage1
"""
import gzip
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import sys

here = Path(__file__).parent
# Reuse the archive parser from the USB diagnostic test without running it.
src = (here / "test_usb_diagnostic.py").read_text().split("control, diagnostic =")[0]
ns = {}
exec(src, ns)
entries = ns["entries"]

tablet = "--tablet" in sys.argv
args = [a for a in sys.argv[1:] if a != "--tablet"]
control, stage = map(Path, args[:2])
for name in ("Pongo.bin", "m1n1.bin", "t7001-j81.dtb", "Image.gz", "bootargs"):
    assert (stage / name).read_bytes() == (control / name).read_bytes(), name

original = gzip.decompress((control / "initramfs.gz").read_bytes())
modified = gzip.decompress((stage / "initramfs.gz").read_bytes())
assert modified.startswith(original), "control archive must stay a byte-identical prefix"
added = entries(modified[len(original):])
before = entries(original)
hook = "etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh"
assert "etc/deviceinfo" not in added, "must not touch the ECM deviceinfo override"

# Allow-list: hook, account state, key, and the Nix-store closure only.
fixed = {hook, "etc/passwd", "etc/group", "root", "root/.ssh",
         "root/.ssh/authorized_keys", "var", "var/empty", "var/run", "var/log", "etc",
         "etc/postmarketos-mkinitfs", "etc/postmarketos-mkinitfs/hooks",
         "usr", "usr/bin", "usr/bin/tablet-status"}
if tablet:
    fixed.add("usr/bin/charging-policy")
extra = {n for n in added if n not in fixed and n not in ("nix", "nix/store") and not n.startswith("nix/store/")}
assert not extra, f"unexpected overlay entries: {sorted(extra)}"
changed = {n for n in added if n in before and before[n][2] != added[n][2] and n != hook}
assert not changed, f"overlay rewrote base files: {sorted(changed)}"

ts = added["usr/bin/tablet-status"]
assert ts[0] & 0o777 == 0o755 and ts[2] == (here / "tablet-status.sh").read_bytes()
if tablet:
    cp = added["usr/bin/charging-policy"]
    assert cp[0] & 0o777 == 0o755 and cp[2] == (here / "charging-policy.sh").read_bytes()
script = added[hook][2]
assert added[hook][0] & 0o777 == 0o755
subprocess.run(["sh", "-n"], input=script, check=True)
text = script.decode()
assert "@DROPBEAR@" not in text
assert re.search(r"^DB=/nix/store/\S+-dropbear-\S*[\d.]+$", text, re.M)
assert "telnetd" in text and text.rstrip().endswith("loop_forever"), "recovery + non-returning"
policy = "/usr/bin/charging-policy >/var/log/charging-policy.log 2>&1 &"
assert (policy in text) == tablet, "charging policy start only in the tablet payload"
if tablet:
    assert text.rstrip().splitlines()[-2] == policy, "policy starts just before the hold loop"
assert "-s -j -k" in text and '"${IP}:${SSH_PORT}"' in text
assert added["root/.ssh/authorized_keys"][0] & 0o777 == 0o600
assert added["root"][0] & 0o777 == 0o700 and added["root/.ssh"][0] & 0o777 == 0o700
key = added["root/.ssh/authorized_keys"][2].decode().strip()
assert key.startswith("ssh-ed25519 ") and "PRIVATE" not in key and "\n" not in key
assert added["etc/passwd"][2].startswith(b"root:x:0:0:")

# Every ELF in the closure: interpreter, DT_NEEDED and RUNPATH must resolve.
def resolve(name):
    seen = set()
    while name in added and added[name][0] & 0o170000 == 0o120000:
        assert name not in seen
        seen.add(name)
        target = added[name][2].decode()
        name = target.lstrip("/") if target.startswith("/") else str(
            (Path(name).parent / target).as_posix())
        name = str(Path(name))  # normalises nothing risky: targets are in-store
    return name

def exists(path):
    return path in added or path in before or resolve(path) in added

def dyn(data):
    assert data[:4] == b"\x7fELF" and data[4] == 2 and data[5] == 1
    phoff, = struct.unpack_from("<Q", data, 32)
    phentsize, phnum = struct.unpack_from("<HH", data, 54)
    interp, load, dynamic = None, [], None
    for i in range(phnum):
        t, _f, off, va, _pa, fsz, _m, _a = struct.unpack_from("<IIQQQQQQ", data, phoff + i * phentsize)
        if t == 3:
            interp = data[off:off + fsz].rstrip(b"\0").decode()
        elif t == 1:
            load.append((va, off, fsz))
        elif t == 2:
            dynamic = (off, fsz)
    if not dynamic:
        return interp, [], []
    def v2o(v):
        for va, off, fsz in load:
            if va <= v < va + fsz:
                return off + v - va
        raise AssertionError("bad vaddr")
    needed, rpath, strtab = [], [], None
    ents = [struct.unpack_from("<qQ", data, dynamic[0] + j) for j in range(0, dynamic[1], 16)]
    strtab = next(v for t, v in ents if t == 5)
    def s(o):
        a = v2o(strtab) + o
        return data[a:data.index(b"\0", a)].decode()
    for t, v in ents:
        if t == 1: needed.append(s(v))
        if t in (15, 29): rpath += s(v).split(":")
    return interp, needed, rpath

checked = 0
for name, (mode, _ids, data) in sorted(added.items()):
    if name.startswith("nix/store/") and mode & 0o170000 == 0o100000 and data[:4] == b"\x7fELF":
        interp, needed, rpath = dyn(data)
        if interp:
            assert exists(interp.lstrip("/")), f"{name}: missing interpreter {interp}"
        for lib in needed:
            hits = [r for r in rpath if exists(f"{r.lstrip('/')}/{lib}")]
            assert hits or exists(f"lib/{lib}"), f"{name}: {lib} not found in RUNPATH"
        checked += 1
assert checked >= 2, "expected dropbear and dropbearkey ELFs"
for b in ("dropbear", "dropbearkey"):
    assert any(n.endswith(f"/bin/{b}") for n in added), b

parts = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
assert (stage / "m1n1-linux.bin").read_bytes() == b"".join((stage / p).read_bytes() for p in parts)
for line in (stage / "SHA256SUMS").read_text().splitlines():
    digest, path = line.split()
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
print(f"SSH stage 1 static gate passed: {checked} ELF files, closure resolves, control prefix intact")
