#!/usr/bin/env python3
"""Verify the payload contract with synthetic device trees and files."""
import gzip
from hashlib import sha256
from pathlib import Path
import struct
import tempfile

from test_verify_pcie_payload import dtb
from verify_gpu_pmgr_payload import PARTS, problems


def tree(extra=None):
    gfx = {"compatible": b"apple,t7000-pmgr-pwrstate\0", "reg": struct.pack(">II", 0x20320, 4),
           "#power-domain-cells": struct.pack(">I", 0),
           "experimental,j81-gpu-test-no-poweroff": b""}
    gfx.update(extra or {})
    return dtb(("", {"compatible": b"apple,j81\0"}, [("soc", {}, [("power-management@20e000000", {"reg": struct.pack(">IIII", 2, 0x0e000000, 0, 0x24000)},
                [("power-controller@20320", gfx, [])])])]))


with tempfile.TemporaryDirectory(prefix="gpu-payload-") as directory:
    root = Path(directory)
    payload, control, kernel = (root / part for part in ("payload", "control", "kernel"))
    for path in (payload, control, kernel): path.mkdir()
    for name in ("Pongo.bin", "m1n1.bin", "bootargs", "initramfs.gz"):
        (payload / name).write_bytes(name.encode())
        (control / name).write_bytes(name.encode())
    (kernel / "Image").write_bytes(b"kernel")
    (payload / "Image.gz").write_bytes(gzip.compress(b"kernel"))
    (payload / "t7001-j81.dtb").write_bytes(tree())
    (control / "Image.gz").write_bytes(b"control-kernel")
    (control / "t7001-j81.dtb").write_bytes(b"control-tree")
    control_blob = b"".join((control / p).read_bytes() for p in PARTS)
    (control / "m1n1-linux.bin").write_bytes(control_blob)
    control_hash = sha256(control_blob).hexdigest()
    pongo_hash = sha256((control / "Pongo.bin").read_bytes()).hexdigest()
    def check():
        return problems(payload, control, kernel, control_hash, pongo_hash)
    def seal():
        (payload / "m1n1-linux.bin").write_bytes(b"".join((payload / p).read_bytes() for p in PARTS))
        (payload / "SHA256SUMS").write_text("".join(f"{sha256((payload / n).read_bytes()).hexdigest()}  {n}\n" for n in ("Pongo.bin", "m1n1.bin", "m1n1-linux.bin")))
    seal()
    assert check() == []
    (control / "Pongo.bin").write_bytes(b"changed")
    assert any("Pongo hash mismatch" in p for p in check())
    (control / "Pongo.bin").write_bytes((payload / "Pongo.bin").read_bytes())
    (payload / "bootargs").write_bytes(b"changed")
    seal()
    assert any("bootargs differs" in p for p in check())
    (payload / "bootargs").write_bytes((control / "bootargs").read_bytes())
    (payload / "t7001-j81.dtb").write_bytes(tree({"power-domains": struct.pack(">I", 1)}))
    seal()
    assert any("parent power domain" in p for p in check())
    (payload / "t7001-j81.dtb").write_bytes(tree())
    seal()
    (payload / "m1n1-linux.bin").write_bytes(b"bad")
    assert any("concatenation mismatch" in p for p in check())
print("PASS: GPU payload checks control, kernel, GFX tree, checksums and composition")
