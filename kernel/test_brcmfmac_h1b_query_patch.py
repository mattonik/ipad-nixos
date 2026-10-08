#!/usr/bin/env python3
"""Patch 0071 (brcmfmac H1B: read-only debugfs query interface and hold toggle, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_query_patch.py [--j81-msi-source DIR]

/sys/kernel/debug/brcmfmac-h1b/{query,result}: tcm / core pcie2|cc / shared / rings / console reads only. brcmfmac.h1b_hold=1
keeps the device bound after a setup failure. The failure snapshot also dumps the shared structure, ring info and the
common-ring memory table. No register, TCM or config write may appear in the added code.
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
         "0071-brcmfmac-h1b-readonly-query-interface.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P71 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def strip(plus):
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)


def check_text():
    text = P71.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = strip(plus)
    # Read-only: nothing that writes a register, TCM, config space, rings a doorbell or sends a mailbox word.
    for forbidden in ("write_reg32", "write_tcm", "write_ptr", "write_ram", "pci_write_config", "writel", "iowrite",
                      "memcpy_toio", "ring_bell", "send_mb_data", "request_irq", "free_irq", "msleep", "udelay", "gpiod",
                      "pci_set_master", "pci_clear_master"):
        assert forbidden not in code, forbidden
    # Files: query write-only 0200, result read-only 0400.
    assert 'debugfs_create_file("query", 0200' in plus and 'debugfs_create_file("result", 0400' in plus
    # Bounds and the hold requirement for window-moving reads.
    assert "H1B_Q_TCM_MAX\t\t0x8000" in plus and "len > H1B_Q_TCM_MAX" in plus
    assert "off >= 0x1000 || len > 0x1000 - off" in plus
    assert "len > devinfo->ci->ramsize - off" in plus
    run = code[code.index("static void h1b_q_run"):code.index("static ssize_t h1b_q_write")]
    assert run.index("h1b_hold_mask") < run.index("h1b_q_core(")
    assert "BCMA_CORE_PCIE2" in run and "BCMA_CORE_CHIPCOMMON" in run and "BCMA_CORE_ARM" not in run
    # Core reads restore the PCIe2 window with the interrupt held off.
    core = code[code.index("static void h1b_q_core"):code.index("static void h1b_q_run")]
    assert core.index("disable_irq(") < core.index("brcmf_pcie_select_core(devinfo, coreid)") < core.index("brcmf_pcie_read_reg32") \
        < core.index("brcmf_pcie_select_core(devinfo, BCMA_CORE_PCIE2)") < core.index("enable_irq(")
    # Hold toggle only skips the driver release, everything else in the failure path is unchanged.
    assert "if (h1b_hold_device())" in plus and "return;" in plus
    assert "h1b_query_init(devinfo);" in plus and "h1b_query_exit(devinfo);" in plus
    assert "h1b_dump_shared_regions(devinfo);" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p71-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        # Definition before use in the real file (the host cannot see use-before-define; the Nix build is the gate).
        assert src.index("static void h1b_dump_rings(") < src.index("static void h1b_q_run")
        assert src.index("brcmf_pcie_select_core(struct brcmf_pciedev_info") < src.index("static void h1b_q_core")
        assert src.index("static void h1b_dump_region(") < src.index("static void h1b_dump_shared_regions(") < src.index("static void h1b_dump_rings(")
        assert src.index("static void h1b_query_init(") < src.index("\th1b_query_init(devinfo);")
        assert src.index("static void h1b_query_exit(") < src.index("\th1b_query_exit(devinfo);")
        assert src.index("static bool h1b_hold_device(") < src.index("if (h1b_hold_device())")
        for stub in ("static inline void h1b_query_init(struct brcmf_pciedev_info *devinfo) { }",
                     "static inline void h1b_query_exit(struct brcmf_pciedev_info *devinfo) { }",
                     "static inline bool h1b_hold_device(void) { return false; }"):
            assert stub in src, stub
        # The query exit runs at the top of remove, before the console read and before devinfo is freed.
        rem = src[src.index("brcmf_pcie_remove(struct pci_dev *pdev)"):]
        assert rem.index("h1b_query_exit(devinfo);") < rem.index("kfree(devinfo);")
        # The release_driver call stays after the hold check.
        setup = src[src.index("Dongle setup failed"):]
        assert setup.index("h1b_hold_device()") < setup.index("device_release_driver(dev);")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0070)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
