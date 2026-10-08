#!/usr/bin/env python3
"""Patch 0075 (brcmfmac H1B: drop the unsafe ChipCommon 0xc40/0xe00 reads, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_safereads_patch.py [--j81-msi-source DIR]

Run 16: with the firmware's Wi-Fi core attached, the machine reset right after the "msi after request_irq" log line, i.e. during the
ChipCommon snapshot (patch 0069) that read 0xc40 and 0xe00 through the BAR0 window. After this patch the ChipCommon snapshot and the
query safe-list read only the standard GPIO block 0x58-0x6c, and no snapshot is taken right after request_irq.
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
         "0071-brcmfmac-h1b-readonly-query-interface.patch", "0072-brcmfmac-h1b-ring-ids-and-safe-register-reads.patch",
         "0073-brcmfmac-h1b-query-snapshot-arm-and-gated-rom.patch", "0074-brcmfmac-h1b-deferred-pcie-registration.patch",
         "0075-brcmfmac-h1b-drop-unsafe-chipcommon-reads.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P75 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def check_text():
    text = P75.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    minus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("-") and not l.startswith("---"))
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    assert "0xc40" in minus and "0xe00" in minus
    assert "static const u16 offs[] = { 0x58, 0x5c, 0x60, 0x64, 0x68, 0x6c };" in plus
    assert 'h1b_log_chipcommon_gpio(devinfo, "after request_irq");' in minus
    assert "return off >= 0x58 && off <= 0x6c;" in plus
    for forbidden in ("write_reg32", "write_tcm", "pci_write_config", "writel", "iowrite", "ring_bell"):
        assert forbidden not in plus, forbidden


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p75-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        # No read of the two registers survives anywhere in the driver code, and no snapshot after request_irq.
        assert "0xc40" not in code and "0xe00" not in code
        assert 'h1b_log_chipcommon_gpio(devinfo, "after request_irq")' not in src
        assert src.count('h1b_log_chipcommon_gpio(devinfo, "at snapshot")') == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0074)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
