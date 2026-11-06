#!/usr/bin/env python3
"""Check a GPU power-test payload against its kernel and known-good RAM control."""
import argparse
import gzip
from hashlib import sha256
from pathlib import Path
import struct

from verify_pcie_j81_reg_on_payload import fdt_nodes

PARTS = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
CONTROL_PARTS = ("Pongo.bin", "m1n1.bin", "bootargs", "initramfs.gz")
GFX = "/soc/power-management@20e000000/power-controller@20320"
CONTROL_SHA256 = "b3206c51c096d9e0cb47473cdcd88157acf677388805eb3532df071ce7315781"
PONGO_SHA256 = "1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575"


def problems(payload, control, kernel, control_hash=CONTROL_SHA256, pongo_hash=PONGO_SHA256):
    errors = []
    parts = {name: (payload / name).read_bytes() for name in PARTS}
    control_blob = (control / "m1n1-linux.bin").read_bytes()
    if sha256(control_blob).hexdigest() != control_hash:
        errors.append("known-good control payload hash mismatch")
    if sha256((control / "Pongo.bin").read_bytes()).hexdigest() != pongo_hash:
        errors.append("known-good Pongo hash mismatch")
    if control_blob != b"".join((control / name).read_bytes() for name in PARTS):
        errors.append("known-good control components do not match its payload")
    for name in CONTROL_PARTS:
        if (payload / name).read_bytes() != (control / name).read_bytes():
            errors.append(f"{name} differs from the known-good control")
    if (payload / "m1n1-linux.bin").read_bytes() != b"".join(parts[name] for name in PARTS):
        errors.append("payload concatenation mismatch")
    if gzip.decompress(parts["Image.gz"]) != (kernel / "Image").read_bytes():
        errors.append("kernel image differs from the test kernel")
    expected_names = {"Pongo.bin", "m1n1.bin", "m1n1-linux.bin"}
    found = set()
    for line in (payload / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split()
        name = Path(path).name
        if name not in expected_names or name in found:
            errors.append(f"unexpected or duplicate checksum entry: {name}")
            continue
        found.add(name)
        if sha256((payload / name).read_bytes()).hexdigest() != digest:
            errors.append(f"checksum mismatch: {name}")
    if found != expected_names:
        errors.append("missing checksum entries")
    if len(parts["t7001-j81.dtb"]) < 40 or struct.unpack_from(">I", parts["t7001-j81.dtb"])[0] != 0xd00dfeed:
        raise ValueError("invalid device tree header")
    nodes = fdt_nodes(parts["t7001-j81.dtb"])
    if b"apple,j81\0" not in nodes.get("/", {}).get("compatible", b""):
        errors.append("root is not J81")
    gfx = nodes.get(GFX, {})
    parent = nodes.get("/soc/power-management@20e000000", {})
    if parent.get("reg") != struct.pack(">IIII", 2, 0x0e000000, 0, 0x24000):
        errors.append("unexpected PMGR controller register range")
    if b"apple,t7000-pmgr-pwrstate\0" not in gfx.get("compatible", b""):
        errors.append("missing GFX PMGR compatibility")
    if gfx.get("reg") != struct.pack(">II", 0x20320, 4):
        errors.append("unexpected GFX PMGR register range")
    if gfx.get("#power-domain-cells") != struct.pack(">I", 0):
        errors.append("unexpected GFX power-domain cell count")
    if "power-domains" in gfx:
        errors.append("GFX has a parent power domain")
    if gfx.get("experimental,j81-gpu-test-no-poweroff") != b"":
        errors.append("missing test-only GFX power-off guard")
    if gfx.get("status", b"okay\0") not in (b"ok\0", b"okay\0"):
        errors.append("GFX PMGR provider is disabled")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("control", type=Path)
    parser.add_argument("kernel", type=Path)
    args = parser.parse_args()
    try:
        errors = problems(args.payload, args.control, args.kernel)
    except (OSError, EOFError, ValueError, AssertionError, struct.error) as error:
        parser.exit(1, f"verification failed: {error}\n")
    if errors:
        parser.exit(1, "verification failed:\n" + "\n".join(errors) + "\n")
    print("PASS: payload composition, test kernel, GFX guard and RAM-control components")


if __name__ == "__main__":
    main()
