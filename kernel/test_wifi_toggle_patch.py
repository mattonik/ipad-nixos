#!/usr/bin/env python3
"""Patch 0067 (J81 Wi-Fi deep-sleep ACK and DEVICE_WAKE toggles, TEST kernels only).

Usage: python3 kernel/test_wifi_toggle_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation; 0065 and 0066 are applied first (the patch sits on
top of them), then 0067, all with zero fuzz. Contract: both behaviours are off unless a boot argument is
given (`pcie_apple_t7000.device_wake=1`, `brcmfmac.h1b_ds_ack=1|2`), the stock deep-sleep ACK is the
default branch, the only added writes are the DEVICE_WAKE GPIO output and the mode-2 mailbox word and
doorbell, and the PCIe driver's register/delay trace is unchanged with the option off.
"""
import argparse
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCHES = [HERE / "patches" / n for n in ("0065-brcmfmac-pcie-h1b-diag.patch",
                                           "0066-readonly-debugfs-diag-dart-and-t7000-port.patch",
                                           "0067-j81-wifi-deep-sleep-and-device-wake-toggles.patch")]
P67 = PATCHES[2]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")
TOUCHED = ("arch/arm64/boot/dts/apple/t7001.dtsi", B + "pcie.c", "drivers/pci/controller/Kconfig",
           "drivers/pci/controller/pcie-apple-t7000.c")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = P67.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == list(TOUCHED)
    plus = added(text)
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    for sym in ("config PCIE_APPLE_T7000_DEVICE_WAKE_TEST", "#ifdef CONFIG_PCIE_APPLE_T7000_DEVICE_WAKE_TEST",
                "#ifdef CONFIG_BRCMFMAC_PCIE_H1B_DIAG", "device-wake-gpios = <&pinctrl 165 GPIO_ACTIVE_HIGH>;"):
        assert sym in plus, sym
    # Both toggles are boot-argument parameters, default off.
    assert re.search(r"static bool t7000_device_wake;", plus) and "module_param_named(device_wake, t7000_device_wake, bool, 0444)" in plus
    assert "static int h1b_ds_ack_mode;" in plus and "module_param_named(h1b_ds_ack, h1b_ds_ack_mode, int, 0444)" in plus
    assert "if (!t7000_device_wake)\n\t\treturn;" in plus
    # Mode 0 (default) is the stock ACK; mode 1 acknowledges nothing; mode 2 is the only new mailbox write.
    assert "default:\n\t\tbrcmf_pcie_send_mb_data(devinfo, BRCMF_H2D_HOST_DS_ACK);" in plus
    assert "case 1:" in plus and "case 2:" in plus
    assert code.count("brcmf_pcie_write_tcm32(") == 1 and code.count("brcmf_pcie_write_reg32(") == 1
    assert "h2d_mailbox_1, 1)" in plus
    # The GPIO output is requested once, high, only inside the test function; nothing else drives a pin.
    assert code.count("GPIOD_OUT_HIGH") == 1 and "gpiod_set_value" not in code and "gpiod_direction_output" not in code
    # No PMU, no config-space or other register writes, no extra delays.
    for forbidden in ("writel", "iowrite", "pci_write_config", "msleep", "udelay", "t7000_pcie_write32", "i2c", "regmap"):
        assert forbidden not in code, forbidden
    assert plus.count("h1b_send_ds_ack(devinfo);") == 1


def apply_all(source, tmp):
    tree = Path(tmp)
    for rel in SRC_FILES:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source) / rel, tree / rel)
        (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
    for p in PATCHES:
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
        assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
    return tree


def check_apply(source):
    spec = importlib.util.spec_from_file_location("seq", HERE / "test_pcie_write_sequence.py")
    seq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq)
    with tempfile.TemporaryDirectory(prefix="toggle-p67-") as tmp:
        tree = apply_all(source, tmp)
        pcie = (tree / TOUCHED[3]).read_text()
        assert seq.normalize(seq.run_trace(tree / TOUCHED[3])) == seq.normalize(seq.GOLDEN.read_text()), \
            "option off must not change the PCIe register trace"
        # Definition before use in both files.
        assert pcie.index("static void t7000_pcie_device_wake") < pcie.index("\tt7000_pcie_device_wake(dev);")
        brcm = (tree / TOUCHED[1]).read_text()
        assert brcm.index("static void h1b_send_ds_ack") < brcm.index("\t\th1b_send_ds_ack(devinfo);")
        # The stock send_mb_data is defined before the helper that falls back to it.
        assert brcm.index("brcmf_pcie_send_mb_data(struct brcmf_pciedev_info") < brcm.index("static void h1b_send_ds_ack")
        assert "device-wake-gpios" in (tree / TOUCHED[0]).read_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065/0066 + trace unchanged with the option off)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
