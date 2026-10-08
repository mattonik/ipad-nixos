#!/usr/bin/env python3
"""Patch 0072 (brcmfmac H1B: Apple ring id/type words, safe-register list for core reads, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_ringids_patch.py [--j81-msi-source DIR]

brcmfmac.h1b_ring_ids=1 writes Apple's id/type word into each common ring's memory-table entry (one TCM word per ring,
word0 of the 16-byte entry). The query interface's core reads are limited to registers read safely before.
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
         "0069-brcmfmac-h1b-chipcommon-gpio-snapshot.patch", "0070-brcmfmac-h1b-apple-shared-memory-parity.patch",
         "0071-brcmfmac-h1b-readonly-query-interface.patch", "0072-brcmfmac-h1b-ring-ids-and-safe-register-reads.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P72 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def strip(plus):
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)


def check_text():
    text = P72.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = strip(plus)
    # The only write is the one ring word; nothing else writes registers, config space or rings a doorbell.
    for forbidden in ("write_reg32", "write_tcm16", "write_ptr", "write_ram", "pci_write_config", "writel", "iowrite", "ring_bell",
                      "send_mb_data", "request_irq", "free_irq", "msleep", "udelay", "gpiod"):
        assert forbidden not in code, forbidden
    assert code.count("brcmf_pcie_write_tcm32(") == 1
    assert "0x00000000, 0x00020001, 0x00010000, 0x00040001, 0x00030002" in plus
    assert "module_param_named(h1b_ring_ids, h1b_ring_ids_on, uint, 0444)" in plus
    assert "if (!h1b_ring_ids_on)" in plus and "h1b_write_ring_idtype(devinfo, ring_id, tcm_ring_phys_addr);" in plus
    # Safe-register list: PCIe2 only mailbox/interrupt registers, ChipCommon only the GPIO block plus 0xc40/0xe00.
    assert "off == 0x20 || off == 0x24 || off == 0x48 || off == 0x4c || off == 0x140 || off == 0x144" in plus
    assert "(off >= 0x58 && off <= 0x6c) || off == 0xc40 || off == 0xe00" in plus
    assert "h1b_q_reg_ok(id, off + len2)" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p72-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        assert src.index("static void h1b_write_ring_idtype(") < src.index("\th1b_write_ring_idtype(devinfo, ring_id, tcm_ring_phys_addr);")
        assert src.index("static bool h1b_q_reg_ok(") < src.index("h1b_q_reg_ok(id, off + len2)")
        assert "static inline void h1b_write_ring_idtype(struct brcmf_pciedev_info *devinfo, u32 ring_id, u32 tcm_ring_phys_addr) { }" in src
        # The id/type word comes after max items and item length were written, and the table is the Linux ring numbering.
        alloc = src[src.index("brcmf_pcie_alloc_dma_and_ring(struct"):]
        assert alloc.index("BRCMF_RING_LEN_ITEMS_OFFSET") < alloc.index("h1b_write_ring_idtype(devinfo")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0071)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
