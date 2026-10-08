#!/usr/bin/env python3
"""Patch 0074 (brcmfmac H1B: deferred PCIe driver registration, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_defer_patch.py [--j81-msi-source DIR]

brcmfmac.h1b_defer_s=N registers the PCIe driver N seconds after init (delayed work) so the host can stream the kernel log
before the Wi-Fi path runs. Default 0 = register immediately, exactly as before. No register access of its own.
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
         "0073-brcmfmac-h1b-query-snapshot-arm-and-gated-rom.patch", "0074-brcmfmac-h1b-deferred-pcie-registration.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P74 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def check_text():
    text = P74.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    for forbidden in ("write_reg32", "write_tcm", "pci_write_config", "writel", "iowrite", "ring_bell", "gpiod", "msleep", "udelay"):
        assert forbidden not in code, forbidden
    assert "module_param_named(h1b_defer_s, h1b_defer_s, uint, 0444)" in plus
    assert "if (h1b_defer_s) {" in plus and "schedule_delayed_work(&h1b_defer_work, h1b_defer_s * HZ);" in plus
    assert "cancel_delayed_work_sync(&h1b_defer_work);" in plus
    # Default behaviour unchanged: the immediate registration call is still the last statement of brcmf_pcie_register().
    assert "\treturn pci_register_driver(&brcmf_pciedrvr);" in text


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p74-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        reg = src.index("int brcmf_pcie_register(void)")
        assert src.index("static struct pci_driver brcmf_pciedrvr") < src.index("static void h1b_deferred_register") < reg
        assert src.index("static DECLARE_DELAYED_WORK(h1b_defer_work") < reg
        ext = src.index("void brcmf_pcie_exit(void)")
        assert src.index("cancel_delayed_work_sync(&h1b_defer_work)") > ext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0073)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
