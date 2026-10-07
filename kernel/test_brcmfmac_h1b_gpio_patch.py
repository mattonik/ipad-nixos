#!/usr/bin/env python3
"""Patch 0069 (brcmfmac H1B: read-only ChipCommon GPIO snapshot, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_gpio_patch.py [--j81-msi-source DIR]

Reads ChipCommon gpiopullup/pulldown/in/out/outen/control (0x58..0x6c) plus 0xc40 and 0xe00 through the BAR0 window, with the
interrupt held off, then restores the window to PCIe2. No register writes besides the stock window selection.
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
         "0069-brcmfmac-h1b-chipcommon-gpio-snapshot.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P69 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def check_text():
    text = P69.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    for forbidden in ("write_reg32", "write_tcm", "write_ptr", "pci_write_config", "writel", "iowrite", "ring_bell",
                      "send_mb_data", "request_irq", "free_irq", "msleep", "udelay", "gpiod", "WRITECC32"):
        assert forbidden not in code, forbidden
    assert re.search(r"offs\[\] = \{ 0x58, 0x5c, 0x60, 0x64, 0x68, 0x6c, 0xc40, 0xe00 \}", plus)
    assert code.count("brcmf_pcie_read_reg32(devinfo, offs[i])") == 1
    assert code.index("BCMA_CORE_CHIPCOMMON") < code.index("brcmf_pcie_read_reg32") < code.index("BCMA_CORE_PCIE2")
    assert code.count("disable_irq(") == 1 and code.count("enable_irq(") == 1
    assert "h1b_log_chipcommon_gpio(devinfo, \"at snapshot\")" in plus
    assert "h1b_log_chipcommon_gpio(devinfo, \"after request_irq\")" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p69-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        assert src.index("brcmf_pcie_select_core(struct brcmf_pciedev_info") < src.index("static void h1b_log_chipcommon_gpio")
        assert src.index("static void h1b_log_chipcommon_gpio") < src.index("\th1b_log_chipcommon_gpio(devinfo, \"at snapshot\");")
        assert src.index("static void h1b_log_chipcommon_gpio") < src.index("\th1b_log_chipcommon_gpio(devinfo, \"after request_irq\");")
        assert "static inline void h1b_log_chipcommon_gpio(struct brcmf_pciedev_info *devinfo, const char *when) { }" in src


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0068)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
