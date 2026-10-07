#!/usr/bin/env python3
"""Patch 0070 (brcmfmac H1B: Apple shared-memory parity toggle, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_shared_patch.py [--j81-msi-source DIR]

Boot parameter brcmfmac.h1b_apple_shared (bit mask, default 0 = stock): 1 no ring-update buffer, 2 4 KiB scratch,
4 Apple ring depths 128/256/128/256/256. No new register access; only the sizes/addresses the host publishes change.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
NAMES = ("0065-brcmfmac-pcie-h1b-diag.patch", "0066-readonly-debugfs-diag-dart-and-t7000-port.patch",
         "0067-j81-wifi-deep-sleep-and-device-wake-toggles.patch", "0068-brcmfmac-h1b-console-poll-and-shared-state.patch",
         "0069-brcmfmac-h1b-chipcommon-gpio-snapshot.patch",
         "0070-brcmfmac-h1b-apple-shared-memory-parity.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P70 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def check_text():
    text = P70.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    for forbidden in ("write_reg32", "pci_write_config", "writel", "iowrite", "ring_bell", "send_mb_data", "request_irq",
                      "free_irq", "msleep", "udelay", "gpiod"):
        assert forbidden not in code, forbidden
    assert "{ 128, 256, 128, 256, 256 }" in plus
    assert "module_param_named(h1b_apple_shared, h1b_apple_shared_mask, uint, 0444)" in plus
    assert "H1B_SHARED_NO_RINGUPD\t1" in plus and "H1B_SHARED_SCRATCH_4K\t2" in plus and "H1B_SHARED_APPLE_DEPTH\t4" in plus
    assert "4096 : BRCMF_DMA_D2H_SCRATCH_BUF_LEN" in plus
    assert plus.count("h1b_ring_max_item(ring_id)") == 3 or text.count("h1b_ring_max_item(ring_id)") >= 3
    assert "h1b_skip_ringupd()" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p70-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        # Helpers are defined before every use; no stock constant is left in the allocation paths.
        first = src.index("static u32 h1b_ring_max_item")
        assert first < src.index("brcmf_pcie_alloc_dma_and_ring(struct")
        assert src.index("static u32 h1b_scratch_len") < src.index("brcmf_pcie_release_scratchbuffers")
        assert src.index("static bool h1b_skip_ringupd") < src.index("if (h1b_skip_ringupd())")
        alloc = src[src.index("brcmf_pcie_alloc_dma_and_ring(struct"):]
        alloc = alloc[:alloc.index("\n}\n")]
        assert "brcmf_ring_max_item[" not in alloc
        fns = src[src.index("brcmf_pcie_release_scratchbuffers"):]
        fns = fns[:fns.index("static int brcmf_pcie_init_scratchbuffers") + 3000]
        assert "BRCMF_DMA_D2H_SCRATCH_BUF_LEN" not in fns
        assert "static inline bool h1b_skip_ringupd(void) { return false; }" in src


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0069)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
