#!/usr/bin/env python3
"""Host test for boot/assemble_private_wifi_payload.py using synthetic assets only (no real firmware)."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import assemble_private_wifi_payload as A  # noqa: E402
from verify_pcie_j81_reg_on_payload import cpio_entries  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


def base_cpio(extra=()):
    entries = [("etc", 0o040755, b""), ("etc/deviceinfo", 0o100644, b'deviceinfo_usb_rndis_function="ecm.usb0"\n')]
    entries += list(extra)
    return b"".join(A.newc_entry(n, m, d) for n, m, d in entries) + A.newc_entry("TRAILER!!!", 0)


def make_public(tmp, extra=()):
    pub = tmp / "public"
    pub.mkdir()
    parts = {"m1n1.bin": b"M1N1" * 10, "bootargs": b"chosen.bootargs=console=tty0 brcmfmac.debug=0x001c0004\n",
             "t7001-j81.dtb": b"DTB" * 7, "Image.gz": b"IMG" * 9, "initramfs.gz": gzip.compress(base_cpio(extra), mtime=0)}
    for n, d in parts.items():
        (pub / n).write_bytes(d)
    order = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
    (pub / "m1n1-linux.bin").write_bytes(b"".join(parts[n] for n in order))
    (pub / "SHA256SUMS").write_text("".join(f"{sha((pub / n).read_bytes())} {pub / n}\n" for n in order))
    return pub


NVRAM = b"".join(f"key{i} = value{i} \r\n".encode() for i in range(12)) + b"# comment\n\n"


def make_assets(tmp):
    d = tmp / "assets"
    d.mkdir()
    for name in A.BINARIES:
        (d / name).write_bytes(os.urandom(64) + name.encode())
    (d / A.NVRAM_NAME).write_bytes(NVRAM)
    return d


def expect_exit(fn, fragment):
    try:
        fn()
    except SystemExit as e:
        assert fragment in str(e), (fragment, str(e))
        return
    raise AssertionError(f"expected refusal: {fragment}")


def main():
    # NVRAM handling.
    staged = A.normalize_nvram(NVRAM)
    assert staged.startswith(b"key0=value0\nkey1=value1\n") and b"\r" not in staged and b"\n\n" not in staged and b"# comment" in staged
    expect_exit(lambda: A.check_nvram(b"   \n"), "empty")
    expect_exit(lambda: A.check_nvram(b"a=1\n\xff\n"), "non-text")
    expect_exit(lambda: A.check_nvram(b"a=1\nb=2\n"), "only 2 key=value")
    expect_exit(lambda: A.check_nvram(b"=x\n" + NVRAM), "empty key")

    # newc writer round-trips through the verifier's parser, appended after a base archive.
    ov = A.build_overlay([("brcmfmac4350c2-pcie.bin", b"BIN" * 5), ("brcmfmac4350c2-pcie.txt", b"a=1\n")])
    ent = cpio_entries(base_cpio() + ov)
    assert ent["lib/firmware/brcm/brcmfmac4350c2-pcie.bin"][1] == b"BIN" * 5 and ent["etc/deviceinfo"][1]

    # End to end with synthetic assets, inside the ignored private directory.
    private = A.ROOT.joinpath(*A.PRIVATE_SUBDIR)
    private.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="test-assemble-", dir=private))
    try:
        tmp = Path(tempfile.mkdtemp(prefix="asm-"))
        pub, assets = make_public(tmp), make_assets(tmp)
        out = work / "payload"
        # Real-asset hash check refuses synthetic data.
        expect_exit(lambda: A.assemble(pub, assets, work / "x1"), "does not match the recorded")
        # Output outside the private tree is refused; so is a non-ignored location.
        expect_exit(lambda: A.assemble(pub, assets, tmp / "out", check_hashes=False), "must be under")
        manifest = A.assemble(pub, assets, out, check_hashes=False, token="0" * 32)
        problems, m = A.verify(out)
        assert not problems, problems
        assert oct((out / "m1n1-linux.bin").stat().st_mode & 0o777) == "0o600"
        assert (out / "PRIVATE_MANIFEST.json").stat().st_mode & 0o077 == 0
        blob = (out / "m1n1-linux.bin").read_bytes()
        assert sha(blob) == manifest["final_m1n1_linux_sha256"]
        # The public parts other than bootargs/initramfs are untouched, in order.
        assert blob.startswith(b"M1N1" * 10 + b"chosen.bootargs=") and b"DTB" * 7 in blob and b"IMG" * 9 in blob
        assert b"j81.run_id=" + b"0" * 32 in blob and b"brcmfmac.debug=0x001c0004" in blob
        ent = cpio_entries(gzip.decompress((out / "initramfs.gz").read_bytes()))
        names = {n for n in ent if n.startswith("lib/firmware/brcm/") and not n.endswith("/")}
        assert names == {"lib/firmware/brcm/" + a["staged"] for a in manifest["assets"]} and len(names) == 4
        nv = ent["lib/firmware/brcm/brcmfmac4350c2-pcie.txt"][1]
        assert nv and nv.count(b"=") >= 12 and sha(nv) == next(a["sha256"] for a in manifest["assets"] if a["staged"].endswith(".txt"))
        # A second run into the same directory is refused; no overwrite.
        expect_exit(lambda: A.assemble(pub, assets, out, check_hashes=False), "not empty")
        # Verification catches tampering and policy violations.
        (out / "m1n1-linux.bin").chmod(0o600)
        tampered = bytearray(blob); tampered[-1] ^= 1
        (out / "m1n1-linux.bin").write_bytes(bytes(tampered))
        assert any("hash differs" in p for p in A.verify(out)[0])
        (out / "m1n1-linux.bin").write_bytes(blob)
        # Base initramfs with a Wi-Fi supplicant, or stray generic firmware: verification must flag both.
        cases = [("supplicant", [("usr/sbin/wpa_supplicant", 0o100755, b"x")], "client/scan tools"),
                 ("generic-fw", [("lib/firmware/brcm/brcmfmac4350-pcie.txt", 0o100644, b"a=1\n")], "extra firmware")]
        for tag, extra, frag in cases:
            pub2 = make_public(Path(tempfile.mkdtemp(prefix="asm2-")), extra)
            out2 = work / ("case-" + tag)
            A.assemble(pub2, assets, out2, check_hashes=False)
            found = A.verify(out2)[0]
            assert any(frag in p for p in found), (tag, found)
        # Allowlisted test toggles are appended before the run token and recorded; anything else is refused.
        out3 = work / "toggles"
        m3 = A.assemble(pub, assets, out3, check_hashes=False, extra_bootargs=("pcie_apple_t7000.device_wake=1", "brcmfmac.h1b_ds_ack=2"))
        m4 = A.assemble(pub, assets, work / "aspm", check_hashes=False, extra_bootargs=("pcie_aspm.policy=performance",))
        assert "pcie_aspm.policy=performance j81.run_id=" in m4["bootargs"]
        for ok in ("pcie_aspm=off", "pcie_aspm.policy=powersave"):
            A.compose({"bootargs": b"x\n", "initramfs.gz": __import__("gzip").compress(b"")}, ("bootargs", "initramfs.gz"), b"", "t", (ok,))
        assert m3["extra_bootargs"] == ["pcie_apple_t7000.device_wake=1", "brcmfmac.h1b_ds_ack=2"]
        assert "pcie_apple_t7000.device_wake=1 brcmfmac.h1b_ds_ack=2 j81.run_id=" in m3["bootargs"] and not A.verify(out3)[0]
        for bad in ("pcie_apple_t7000.device_wake=2", "brcmfmac.h1b_ds_ack=3", "brcmfmac.h1b_apple_shared=8", "brcmfmac.h1b_hold=2", "brcmfmac.h1b_ring_ids=2", "brcmfmac.h1b_defer_s=1000", "apple_dart.pci_rebase=2", "brcmfmac.h1b_fast_poll_us=1", "brcmfmac.h1b_fast_poll_us=123456", "apple_dart.pci_rebase=-1", "brcmfmac.h1b_defer_s=", "init=/bin/sh", "brcmfmac.debug=0", "pcie_aspm.policy=bogus", "pcie_aspm=on"):
            expect_exit(lambda b=bad: A.assemble(pub, assets, work / ("bad" + str(abs(hash(b)) % 1000)), check_hashes=False, extra_bootargs=(b,)), "not an allowed test toggle")
        # A test MAC can be appended to the staged NVRAM (unicast, locally administered only; never twice).
        mm = A.assemble(pub, assets, work / "mac", check_hashes=False, nvram_macaddr="02:6A:38:70:00:01")
        nvm = {a["staged"]: a for a in mm["assets"]}[A.NVRAM_STAGED]
        assert nvm["macaddr_added"] and nvm["macaddr"] == "02:6a:38:70:00:01" and not A.verify(work / "mac")[0]
        ent_m = cpio_entries(gzip.decompress((work / "mac" / "initramfs.gz").read_bytes()))
        assert ent_m["lib/firmware/brcm/" + A.NVRAM_STAGED][1].endswith(b"macaddr=02:6a:38:70:00:01\n")
        for badmac in ("00:11:22:33:44:55", "03:6a:38:70:00:01", "02:6a:38:70:00", "zz:6a:38:70:00:01", "02:00:00:00:00:00"):
            expect_exit(lambda b=badmac: A.assemble(pub, assets, work / ("badmac" + str(abs(hash(b)) % 1000)), check_hashes=False, nvram_macaddr=b), "nvram-macaddr")
        # Bad inputs refuse before anything is written.
        (assets / A.NVRAM_NAME).write_bytes(b"")
        expect_exit(lambda: A.assemble(pub, assets, work / "x2", check_hashes=False), "empty")
        assert not (work / "x2").exists()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("PASS: private Wi-Fi payload assembler (NVRAM rules, newc overlay, private-dir policy, verification, tamper/policy detection)")


if __name__ == "__main__":
    main()
