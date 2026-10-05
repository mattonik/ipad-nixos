#!/usr/bin/env python3
"""Patch 0058 (MSI allocation self-test, TEST KERNELS ONLY): contract and zero-fuzz apply.

Usage: python3 kernel/test_pcie_msi_selftest_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation. The driver only touches the endpoint's
MSI capability through the PCI core, so the checks are: it is opt-in, test-only, never binds
(returns -ENODEV), enables no bus mastering, and writes no config or MMIO register itself.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0058-pcie-apple-t7000-msi-selftest.patch"
NEW = "drivers/pci/controller/pcie-apple-t7000-msi-selftest.c"


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert touched == ["drivers/pci/controller/Kconfig", "drivers/pci/controller/Makefile", NEW], touched
    plus = added(text)
    # Opt-in, built-in only, and depends on the host driver being built in.
    assert "config PCIE_APPLE_T7000_MSI_SELFTEST" in plus and "depends on PCIE_APPLE_T7000=y" in plus
    assert "obj-$(CONFIG_PCIE_APPLE_T7000_MSI_SELFTEST) += pcie-apple-t7000-msi-selftest.o" in plus
    assert "TEST KERNELS ONLY" in plus
    # Expected values are the design's: one vector, doorbell, slots 8..15.
    for fragment in ("pci_alloc_irq_vectors(pdev, 1, 1, PCI_IRQ_MSI)", "0xbffff000UL",
                     "T7000_MSI_SLOT_FIRST\t\t8", "T7000_MSI_SLOT_LAST\t\t15", "return -ENODEV;",
                     "pci_free_irq_vectors(pdev)", "PCI_DEVICE(PCI_VENDOR_ID_BROADCOM, 0x43a3)"):
        assert fragment in plus, fragment
    code = "\n".join(l for l in plus.splitlines() if not l.lstrip().startswith(("/*", "*", "//")))
    # No device or controller writes of its own, no bus mastering, no firmware, no DMA.
    for forbidden in ("pci_write_config", "writel", "writew", "writeb", "pci_set_master", "pci_enable_device",
                      "request_firmware", "dma_", "MSI_FLAG_", "PCI_IRQ_MSIX", "PCI_IRQ_ALL_TYPES",
                      "pci_ioremap", "ioremap", "pmu", "gpiod_"):
        assert forbidden not in code, forbidden
    assert code.count("return 0;") == 0, "the self-test must never stay bound"


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="pcie-p58-") as tmp:
        tree = Path(tmp)
        for rel in ("drivers/pci/controller/Kconfig", "drivers/pci/controller/Makefile"):
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert (tree / NEW).is_file()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
