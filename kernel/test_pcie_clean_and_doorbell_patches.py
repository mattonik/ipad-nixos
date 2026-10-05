#!/usr/bin/env python3
"""Contract and zero-fuzz apply checks for patches 0054 (clean-up) and 0055 (DART doorbell).

Usage: python3 kernel/test_pcie_clean_and_doorbell_patches.py [--j81-dllla-source DIR]

DIR is the source tree of the 0053 kernel derivation (patches 0001-0011, 0016, 0040-0045,
0052, 0053 applied). Without it only the text contracts are checked. The write/read/delay
sequence of 0054 is pinned separately by kernel/test_pcie_write_sequence.py.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

PATCHES = Path(__file__).with_name("patches")
P54 = PATCHES / "0054-pcie-apple-t7000-clean-up.patch"
P55 = PATCHES / "0055-apple-dart-per-controller-msi-doorbell.patch"
DRIVER = "drivers/pci/controller/pcie-apple-t7000.c"
DART = "drivers/iommu/apple-dart.c"
DTSI = "arch/arm64/boot/dts/apple/t7001-air2.dtsi"
YAML = "Documentation/devicetree/bindings/pci/apple,t7000-pcie.yaml"
STALE = ("tuning-baseline-test", "dbi-write-test", "link-wait-test", "link-speed-test",
         "dbi-ecam-read-test", "Stage 4", "Stage 5")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    t54, t55 = P54.read_text(), P55.read_text()
    plus54 = added(t54)
    for stale in STALE:
        assert stale not in plus54, f"0054 still adds {stale!r}"
    # No new write, GPIO, PMU or Bluetooth action is introduced by the clean-up.
    for forbidden in ("writel(", "writeb(", "gpiod_", "regmap_write", "0x0402"):
        assert forbidden not in plus54.replace("writel(v | T7000_PCIE_PORT_CONFIG_LINK_START", ""), forbidden
    assert plus54.count("dev_dbg(") >= 14
    plus55 = added(t55)
    for fragment in ('"apple,msi-doorbell"', "of_property_read_u64", "IS_ENABLED(CONFIG_PCIE_APPLE)",
                     "IOMMU_RESV_MSI", "doorbell & PAGE_MASK",
                     "apple,msi-doorbell = <0x0 0xbffff000>;", "uint64"):
        assert fragment in plus55, fragment
    # 0055 touches only these three files.
    assert sorted(re.findall(r"^diff --git a/(\S+)", t55, flags=re.M)) == sorted([YAML, DTSI, DART])


def apply(tree, patch):
    r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=tree,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def check_apply(source):
    source = Path(source).resolve()
    files = (DRIVER, DART, DTSI, YAML)
    with tempfile.TemporaryDirectory(prefix="pcie-p54-55-") as tmp:
        tree = Path(tmp)
        for rel in files:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        original_dart = (tree / DART).read_text()

        apply(tree, P54)
        driver = (tree / DRIVER).read_text()
        for stale in STALE:
            assert stale not in driver, f"driver still has {stale!r}"
        assert "T7000_PCIE_TEST_PORT" not in driver and "t7000_pcie_log_" not in driver
        assert "t7000-pcie: link active=%d" in driver
        # DLLLA remains the only link criterion; +0x88 is read for a debug dump only.
        wait = driver.split("static void t7000_pcie_wait_link_active", 1)[1].split("static void t7000_pcie_rmw", 1)[0]
        assert "BIT(6)" not in wait and "T7000_PCIE_LNKSTA_DLLLA" in wait
        assert "T7000_PCIE_LINK_UP_BIT" not in driver

        apply(tree, P55)
        dart = (tree / DART).read_text()
        start = "static void apple_dart_get_resv_regions"
        end = "static const struct iommu_ops apple_dart_iommu_ops"
        # Outside the doorbell helper and resv-regions function nothing in apple-dart.c changed.
        def outside(text):
            a = text.index("/*\n * MSI doorbell page of the PCIe host bridge") if "MSI doorbell page of the PCIe host bridge" in text else text.index(start)
            return text[:a] + text[text.index(end, a):]
        assert outside(dart) == outside(original_dart), "0055 changed apple-dart.c outside the resv-regions code"
        assert dart.count("iommu_dma_get_resv_regions(dev, head);") == 1
        # The reserved region keeps the same protection bits as before.
        assert "int prot = IOMMU_WRITE | IOMMU_NOEXEC | IOMMU_MMIO;" in dart
        assert "apple,msi-doorbell = <0x0 0xbffff000>;" in (tree / DTSI).read_text()
        yaml = (tree / YAML).read_text()
        assert yaml.rstrip().endswith("};"), "binding example must be terminated"
        assert "apple,reg-on-pmic:" in yaml and "apple,msi-doorbell:" in yaml
        assert yaml.count("{") == yaml.count("}"), "unbalanced braces in the binding example"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-dllla-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_dllla_source:
        check_apply(args.j81_dllla_source)
    print("PASS" + (" (text contracts + zero-fuzz apply of 0054 and 0055)" if args.j81_dllla_source else " (text contracts only)"))


if __name__ == "__main__":
    main()
