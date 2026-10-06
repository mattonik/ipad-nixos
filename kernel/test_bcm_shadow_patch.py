#!/usr/bin/env python3
"""Patch 0062 (BCM4350 OTP shadow capture, TEST kernels only, private data): contract, apply, trace.

Usage: python3 kernel/test_bcm_shadow_patch.py [--j81-msi-source DIR] [--update-golden]

DIR is the source tree of the 0057 kernel derivation; 0061 and then 0062 are applied with zero
fuzz. Checks: text contract (opt-in, read-only, data never logged); with the Kconfig option off
the trace equals the 0061 golden; with it on, the real driver runs against a fake BCM4350 and the
shadow reads are exactly the span the 40 nm formula derives (contiguous 16-bit reads from
ChipCommon +0x800, never more than 512 words), only for the ChipCommon path with OTP already
selected, with no selector or other write, the window restored and no buffer leak.
"""
import argparse
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zlib

HERE = Path(__file__).parent
P61 = HERE / "patches" / "0061-pcie-apple-t7000-bcm-probe.patch"
P62 = HERE / "patches" / "0062-pcie-apple-t7000-bcm-shadow-capture.patch"
GOLDEN = HERE / "bcm_probe_trace" / "golden-shadow.trace"
DRIVER = "drivers/pci/controller/pcie-apple-t7000-bcm-probe.c"
FILES = ("drivers/pci/controller/Kconfig", "drivers/pci/controller/Makefile")

spec = importlib.util.spec_from_file_location("p61", HERE / "test_bcm_probe_patch.py")
p61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p61)


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = P62.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert touched == ["drivers/pci/controller/Kconfig", DRIVER], touched
    plus = added(text)
    assert "config PCIE_APPLE_T7000_BCM_PROBE_SHADOW" in plus
    assert "depends on PCIE_APPLE_T7000_BCM_PROBE && DEBUG_FS" in plus
    assert "IS_ENABLED(CONFIG_PCIE_APPLE_T7000_BCM_PROBE_SHADOW)" in plus
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    # Read-only and private: no new writes of any kind, the selector bits are only tested, the data
    # is never printed (log lines carry counts and a CRC), a hard 512-word cap, 0400 debugfs file.
    for forbidden in ("iowrite", "writel", "writew", "writeb", "pci_write_config", "pci_set_master",
                      "request_firmware", "dma_", "BCM_CC_SROMCONTROL, ", "otpcontrol", "otpprog",
                      "print_hex_dump", "hex_dump", "%04x", "buf[i])", "pr_info", "brcmf"):
        assert forbidden not in code, forbidden
    assert "BCM_SHADOW_MAX_WORDS	512" in plus and "words > BCM_SHADOW_MAX_WORDS" in code
    assert '"t7000-bcm-otp-shadow", 0400, NULL' in code and "IS_ERR_OR_NULL(file)" in code
    assert "ioread16(bar + BCM_CC_SROMOTP + 2 * i)" in code
    assert code.count("ioread16(") == 1


def apply_tree(source, tmp):
    tree = Path(tmp)
    for rel in FILES:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source) / rel, tree / rel)
        (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
    for patch in (P61, P62):
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, patch.name + "\n" + r.stdout + r.stderr
    return tree


def blocks(trace):
    return p61.scenarios(trace)


# Expected capture word counts per scenario (None: nothing may be read from the shadow).
EXPECT = {
    "ok-rev48-chipcommon": None,            # SPROM present -> refused
    "ok-rev49-gci": None,
    "ok-rev51-chipcommon": 128,             # encoding 1 -> (1+1)*1024/16
    "stop-rev43": None, "stop-chip-4354": None, "stop-chipid-allones": None, "stop-window-rejected": None,
    "stop-eromptr-range": None, "stop-first-component-not-cc": None, "stop-no-component": None,
    "stop-wrap-not-40nm": None, "restore-nondefault-window": None, "fail-enable": None, "fail-region": None,
    "shadow-j81-enc5-384": 384,             # the observed J81 values: 768 bytes
    "shadow-enc7-512": 512,
    "shadow-enc0-refused": None, "shadow-srom-present-refused": None, "shadow-otpsel-clear-refused": None,
    "shadow-gci-refused": None, "shadow-kmalloc-fails": None,
    "shadow-debugfs-fails": 384,            # read, then dropped (buffer freed) when debugfs refuses
    "shadow-device-returns-allones": 384,
}


def check_shadow(trace):
    sc = blocks(trace)
    assert set(sc) == set(EXPECT), sorted(set(sc) ^ set(EXPECT))
    for name, block in sc.items():
        assert "PROBE_RET -19" in block and "VIOLATIONS 0" in block, name
        fin = re.search(r"FINAL_WINDOW (0x[0-9a-f]+) INITIAL (0x[0-9a-f]+)", block)
        assert fin.group(1) == fin.group(2), f"{name}: window not restored"
        assert not re.search(r"CFG[RW] (?!0x80)", block), name
        rd = re.search(r"RD16 count=(\d+) first=(0x[0-9a-f]+) last=(0x[0-9a-f]+) contiguous=(\d)", block)
        n = int(rd.group(1))
        al = re.search(r"ALLOC allocs=(\d+) frees=(\d+) kept=(\d+)", block)
        allocs, frees, kept = map(int, al.groups())
        assert allocs == frees + kept, f"{name}: buffer leak"
        want = EXPECT[name]
        if want is None:
            assert n == 0, f"{name}: shadow read although nothing may be captured"
        else:
            assert n == want and rd.group(2) == "0x800" and int(rd.group(3), 16) == 0x800 + 2 * (want - 1), name
            assert rd.group(4) == "1" and 0x800 + 2 * want <= 0xc00, name   # contiguous, inside the 1 KiB window
        # The data must never reach the log: the harness's fake words are 0xBEEx.
        for line in block.splitlines():
            if line.startswith("LOG"):
                assert "bee" not in line.lower(), f"{name}: data in the log: {line}"
        # Neither the hex nor the decimal form of any fake data word (0xBEE0..0xBEEF) may be logged,
        # and the only counts the capture line carries are the derived span and its byte size.
        for line in block.splitlines():
            if line.startswith("LOG") and re.search(r"\b488(6[4-9]|7\d)\b", line):
                raise AssertionError(f"{name}: data word in the log: {line}")
        cap = re.search(r"captured (\d+) words \((\d+) bytes\)", block)
        if cap:
            assert int(cap.group(1)) == want and int(cap.group(2)) == 2 * want, name
        # Data stays in the ChipCommon window only (the harness flags any other 16-bit read).
    # Captured scenarios publish exactly one root-only blob of the right size with the right CRC.
    for name in ("ok-rev51-chipcommon", "shadow-j81-enc5-384", "shadow-enc7-512", "shadow-device-returns-allones"):
        m = re.search(r"DEBUGFS_BLOB name=t7000-bcm-otp-shadow mode=400 size=(\d+) crc=(0x[0-9a-f]{8})", sc[name])
        assert m, name
        words = EXPECT[name]
        assert int(m.group(1)) == 2 * words
        if name == "shadow-device-returns-allones":
            data = b"\xff\xff" * words
            assert "allones=%d zero=0" % words in sc[name]
        else:
            data = b"".join((0xBEE0 + (i & 0xF)).to_bytes(2, "little") for i in range(words))
        # crc32_le(~0, data) is zlib's crc32 without the final inversion.
        assert int(m.group(2), 16) == (zlib.crc32(data) ^ 0xFFFFFFFF), name
    assert "crc32=0x%08x" % (zlib.crc32(b"".join((0xBEE0 + (i & 0xF)).to_bytes(2, "little") for i in range(384))) ^ 0xFFFFFFFF) in sc["shadow-j81-enc5-384"]
    # Failure handling frees or never allocates; the device is left as before.
    assert "KMALLOC fails" in sc["shadow-kmalloc-fails"] and "DEBUGFS_BLOB" not in sc["shadow-kmalloc-fails"]
    assert "DEBUGFS_BLOB t7000-bcm-otp-shadow fails" in sc["shadow-debugfs-fails"] and "KFREE" in sc["shadow-debugfs-fails"]
    # Refusals say why, in particular that no selector write is ever made on the user's behalf.
    assert "not captured - OTP is not both present and selected (a selector write would be needed; refused)" in sc["shadow-otpsel-clear-refused"]
    assert "not captured - SPROM present" in sc["shadow-srom-present-refused"]
    assert "not captured - OTP size encoding 0" in sc["shadow-enc0-refused"]
    assert "not captured - mapping path is not chipcommon" in sc["shadow-gci-refused"]


def check_apply(source, update):
    with tempfile.TemporaryDirectory(prefix="bcm-shadow-") as tmp:
        tree = apply_tree(source, tmp)
        driver = tree / DRIVER
        # Option off: identical to the 0061 behaviour (the 0061 golden).
        off = p61.run_harness(driver)
        p61.check_invariants(off)
        assert off == p61.GOLDEN.read_text(), "0062 changed the 0061 behaviour with the option off"
        on = p61.run_harness(driver, defines=("HARNESS_SHADOW", "CONFIG_PCIE_APPLE_T7000_BCM_PROBE_SHADOW=1"))
        check_shadow(on)
        if update:
            GOLDEN.write_text(on)
            print(f"golden updated: {GOLDEN} ({len(on.splitlines())} lines)")
        else:
            assert on == GOLDEN.read_text(), "trace differs from golden (review, then --update-golden)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    parser.add_argument("--update-golden", action="store_true")
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source, args.update_golden)
    print("PASS" + (" (text contract + zero-fuzz apply + host trace)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
