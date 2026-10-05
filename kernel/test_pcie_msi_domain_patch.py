#!/usr/bin/env python3
"""Patch 0057 (J81 one-vector MSI parent domain): contract, atomic DT, apply, behaviour.

Usage: python3 kernel/test_pcie_msi_domain_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0056 kernel derivation (0052-0056 applied). With it the patch is
applied with zero fuzz to the whole tree and the patched driver is run through the MSI domain
test (kernel/test_pcie_msi_domain.py) and the default-mode golden write trace.
"""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0057-pcie-apple-t7000-msi-domain.patch"
FILES = ("drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
         "arch/arm64/boot/dts/apple/t7001.dtsi", "arch/arm64/boot/dts/apple/t7001-air2.dtsi",
         "Documentation/devicetree/bindings/pci/apple,t7000-pcie.yaml")
DRIVER = FILES[0]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    # Driver and DT arrive together: the DT's msi-controller is only valid with the domain.
    assert touched == list(FILES), touched
    plus = added(text)
    for fragment in ("msi_create_parent_irq_domain", "DOMAIN_BUS_PCI_MSI", "MSI_CHIP_FLAG_SET_EOI",
                     "msi_lib_init_dev_msi_info", "bitmap_find_free_region(allocated, T7000_PCIE_MSI_NVECS, 0)",
                     "select IRQ_MSI_LIB", "depends on PCI_MSI", "msi-controller;",
                     "msi-ranges = <&aic AIC_IRQ 224 IRQ_TYPE_EDGE_RISING 32>;", "msi-parent = <&pcie>;"):
        assert fragment in plus, fragment
    # One vector only (user decision): no multi-MSI, no MSI-X, no write to the doorbell register.
    code = "\n".join(l for l in plus.splitlines() if not l.lstrip().startswith(("/*", "*", "//")))
    for forbidden in ("MSI_FLAG_MULTI_PCI_MSI", "MSI_FLAG_PCI_MSIX", "writel(", "writew(", "0x168",
                      "0x0402", "gpiod_"):
        assert forbidden not in code, forbidden


def apply_tree(source, tmp):
    tree = Path(tmp)
    for rel in FILES:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source) / rel, tree / rel)
        (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
    r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not list(tree.rglob("*.rej")) and not list(tree.rglob("*.orig"))
    return tree


def check_apply(source):
    seq, msi = load("test_pcie_write_sequence"), load("test_pcie_msi_domain")
    with tempfile.TemporaryDirectory(prefix="pcie-p57-") as tmp:
        tree = apply_tree(source, tmp)
        driver = tree / DRIVER
        air2 = (tree / FILES[3]).read_text()
        assert air2.count("msi-controller;") == 1
        # The default (MSI not declared) trace is still the hardware-proven 0053 sequence.
        assert seq.normalize(seq.run_trace(driver)) == seq.normalize(seq.GOLDEN.read_text()), \
            "0057 changed the non-MSI register sequence"
        msi.check(seq.run_trace(driver, "msi"))
        assert seq.normalize(seq.run_trace(driver, "msi")) == seq.normalize(msi.GOLDEN.read_text()), \
            "MSI trace differs from golden"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply + host behaviour)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    sys.exit(main())
