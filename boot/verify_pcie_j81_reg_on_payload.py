#!/usr/bin/env python3
"""Static verification of the Wi-Fi-only J81 REG_ON staging payload (stdlib only).

Usage: python3 boot/verify_pcie_j81_reg_on_payload.py PAYLOAD_DIR [--dllla | --clean | --doorbell]

--dllla additionally requires the 0053 DLLLA link-wait strings and rejects the old
`link-wait-test: link_up=` poll output. --clean (patch 0054) requires the durable
`t7000-pcie: link active=` string and rejects every test-stage log prefix. --doorbell
(patch 0055) is --clean plus the PCIe node's `apple,msi-doorbell` = 0xbffff000.

Checks the built `m1n1-hoolock-pcie-j81-reg-on` output without any device:
checksums and m1n1-linux.bin composition; the DTB names the D2207 PMIC for the PCIe
node exactly once; the initramfs carries no Bluetooth userland or I2C tools; the
kernel contains the board-gated REG_ON strings and not the earlier test-stage ones.
"""
import gzip
import hashlib
from pathlib import Path
import struct
import sys

I2C_TOOLS = {"i2cget", "i2cset", "i2cdetect", "i2cdump", "i2ctransfer"}
FORBIDDEN_BINARIES = I2C_TOOLS | {"btattach", "hciattach", "hciconfig", "hcitool"}


def cpio_entries(data):
    """Read concatenated newc archives (same parser as boot/test_usb_diagnostic.py)."""
    result, offset = {}, 0
    while offset < len(data):
        if data[offset] == 0:
            offset += 1
            continue
        assert data[offset:offset + 6] == b"070701", offset
        fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        start = offset + 110
        name = data[start:start + namesize - 1].decode().removeprefix("./")
        start = (start + namesize + 3) & ~3
        if name != "TRAILER!!!":
            result[name] = (mode, data[start:start + size])
        offset = (start + size + 3) & ~3
    return result


def fdt_nodes(blob):
    """Return {path: {property: bytes}} for a flattened device tree."""
    magic, _total, off_struct, off_strings = struct.unpack(">4I", blob[:16])
    assert magic == 0xD00DFEED, "not a DTB"
    pos, path, nodes = off_struct, [], {}
    align = lambda x: (x + 3) & ~3  # noqa: E731
    while True:
        tag = struct.unpack(">I", blob[pos:pos + 4])[0]
        pos += 4
        if tag == 1:
            end = blob.index(b"\0", pos)
            path.append(blob[pos:end].decode())
            pos = align(end + 1)
            nodes["/".join(path) or "/"] = {}
        elif tag == 2:
            path.pop()
        elif tag == 3:
            length, nameoff = struct.unpack(">II", blob[pos:pos + 8])
            pos += 8
            name_start = off_strings + nameoff
            name = blob[name_start:blob.index(b"\0", name_start)].decode()
            nodes["/".join(path) or "/"][name] = blob[pos:pos + length]
            pos = align(pos + length)
        elif tag == 9:
            return nodes


def main(argv):
    payload = Path(argv[1])
    flags = set(argv[2:])
    doorbell = "--doorbell" in flags
    clean = "--clean" in flags or doorbell
    dllla = "--dllla" in flags or clean
    problems = []

    # Checksums and composition.
    for line in (payload / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split()
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            problems.append(f"checksum mismatch: {path}")
    parts = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
    if (payload / "m1n1-linux.bin").read_bytes() != b"".join((payload / p).read_bytes() for p in parts):
        problems.append("m1n1-linux.bin is not the concatenation of its parts")

    # DTB: the PMIC phandle appears only on the PCIe node, and resolves to the D2207.
    nodes = fdt_nodes((payload / "t7001-j81.dtb").read_bytes())
    holders = {p: v for p, v in nodes.items() if "apple,reg-on-pmic" in v}
    if len(holders) != 1:
        problems.append(f"apple,reg-on-pmic must appear exactly once, found {sorted(holders)}")
    else:
        (holder, props), = holders.items()
        if "pcie@610000000" not in holder:
            problems.append(f"apple,reg-on-pmic is on {holder}, not the PCIe node")
        handle = struct.unpack(">I", props["apple,reg-on-pmic"])[0]
        targets = [p for p, v in nodes.items() if v.get("phandle") == struct.pack(">I", handle)]
        if len(targets) != 1 or not targets[0].endswith("pmic@3c"):
            problems.append(f"phandle resolves to {targets}, expected the D2207 pmic@3c")
        else:
            compat = nodes[targets[0]].get("compatible", b"")
            if b"apple,i2c-pmic" not in compat:
                problems.append("target is not an apple,i2c-pmic")
        if holders and nodes[holder].get("status", b"").rstrip(b"\0") != b"okay":
            problems.append("PCIe node is not enabled in this payload")
    for forbidden in ("touch", "bluetooth", "bt"):
        for p, v in nodes.items():
            comp = v.get("compatible", b"")
            if b"apple,reg-on" in comp and forbidden in comp.decode(errors="ignore"):
                problems.append(f"unexpected compatible on {p}")

    # initramfs: no Bluetooth userland or I2C tools anywhere.
    entries = cpio_entries(gzip.decompress((payload / "initramfs.gz").read_bytes()))
    present = sorted(n for n in entries if n.rsplit("/", 1)[-1] in FORBIDDEN_BINARIES)
    if present:
        problems.append(f"forbidden binaries in initramfs: {present}")
    if "etc/deviceinfo" not in entries or b"ecm.usb0" not in entries["etc/deviceinfo"][1]:
        problems.append("ECM deviceinfo override missing")

    # Kernel: board-gated strings present, test-stage REG_ON strings absent.
    image = gzip.decompress((payload / "Image.gz").read_bytes())
    for needle in (b"failed to assert declared J81 Wi-Fi REG_ON", b"J81 Wi-Fi REG_ON: 0x%04x"):
        if needle not in image:
            problems.append(f"kernel lacks {needle.decode()!r}")
    for stale in (b"reg-on-test: no PMU node", b"reg-on-test: unexpected config"):
        if stale in image:
            problems.append(f"kernel still has test-stage string {stale.decode()!r}")

    if dllla:
        link_string = b"t7000-pcie: link active=" if clean else b"t7000-pcie link-wait: link active="
        if link_string not in image:
            problems.append(f"kernel lacks the DLLLA link-wait log string {link_string.decode()!r}")
        if b"link-wait-test: link_up=" in image:
            problems.append("kernel still has the +0x88 bit-6 link-up poll output")
    if clean:
        for stale in (b"tuning-baseline-test", b"dbi-write-test", b"link-wait-test", b"link-speed-test",
                      b"dbi-ecam-read-test", b"t7000-pcie link-wait:"):
            if stale in image:
                problems.append(f"kernel still has test-stage string {stale.decode()!r}")
    if doorbell:
        if b"apple,msi-doorbell" not in image:
            problems.append("kernel lacks the apple,msi-doorbell property lookup")
        holder = [p for p, v in nodes.items() if "apple,msi-doorbell" in v]
        if len(holder) != 1 or "pcie@610000000" not in holder[0]:
            problems.append(f"apple,msi-doorbell must be on the PCIe node only, found {holder}")
        else:
            value = nodes[holder[0]]["apple,msi-doorbell"]
            if struct.unpack(">II", value) != (0, 0xBFFFF000):
                problems.append(f"apple,msi-doorbell is {value.hex()}, expected 00000000bffff000")

    if problems:
        print("FAIL")
        for p in problems:
            print(" -", p)
        return 1
    print("PASS: checksums, composition, DT phandle (PCIe node only, resolves to D2207),")
    print("      no btattach/I2C tools in the initramfs, board-gated REG_ON strings only")
    if doorbell:
        print("      clean-up strings only; per-controller MSI doorbell 0xbffff000 on the PCIe node")
    elif clean:
        print("      clean-up strings only (no test-stage log prefixes)")
    elif dllla:
        print("      DLLLA link wait present; the +0x88 bit-6 poll is gone")
    else:
        print("NOTE: the inherited Stage-5F link wait still polls +0x88 bit 6 (technical debt, not a pass/fail signal)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] not in ("--dllla", "--clean", "--doorbell")):
        sys.exit(__doc__)
    sys.exit(main(sys.argv))
