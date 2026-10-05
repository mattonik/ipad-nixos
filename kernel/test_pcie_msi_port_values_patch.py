#!/usr/bin/env python3
"""Patch 0056 (derive the MSI port register values): contract, apply, and trace equality.

Usage: python3 kernel/test_pcie_msi_port_values_patch.py [--j81-clean-source DIR]

DIR is the source tree of the 0054 kernel derivation (0052-0054 applied). With it the patch is
applied with zero fuzz, the real patched driver is compiled into the host harness (so the
static_asserts run), and its read/write/delay trace is compared with the golden 0053 trace.
"""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0056-pcie-apple-t7000-derive-msi-port-values.patch"
DRIVER = "drivers/pci/controller/pcie-apple-t7000.c"


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    plus = added(text)
    for fragment in ("T7000_PCIE_PORT_MSICFG\t\t\t0x124", "T7000_PCIE_PORT_MSIBASE\t\t\t0x128",
                     "T7000_PCIE_MSI_PORT_BASE\t\t8", "T7000_PCIE_MSI_PORT_COUNT\t\t8",
                     "ilog2(T7000_PCIE_MSI_PORT_COUNT)", "static_assert(T7000_PCIE_PORT_MSICFG_VALUE == 0x00000031)",
                     "static_assert(T7000_PCIE_PORT_MSIBASE_VALUE == 0x00080008)",
                     "static_assert(is_power_of_2(T7000_PCIE_MSI_PORT_COUNT))",
                     "#include <linux/build_bug.h>", "#include <linux/log2.h>"):
        assert fragment in plus, fragment
    # The doorbell register is documented as not written, and nothing new is written.
    assert "+0x168" in plus and "not written here" in plus
    for forbidden in ("writel(", "writew(", "writeb(", "regmap_write", "gpiod_", "0x168,", "0x0402"):
        assert forbidden not in plus.replace("t7000_pcie_write32(dev, ctrl", ""), forbidden
    # Exactly the two existing msi writes are rewritten, with the same helper and labels.
    assert plus.count('t7000_pcie_write32(dev, ctrl, "msi"') == 2


def check_apply(source):
    spec = importlib.util.spec_from_file_location("seq", HERE / "test_pcie_write_sequence.py")
    seq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq)
    with tempfile.TemporaryDirectory(prefix="pcie-p56-") as tmp:
        tree = Path(tmp)
        (tree / DRIVER).parent.mkdir(parents=True)
        shutil.copy2(Path(source) / DRIVER, tree / DRIVER)
        (tree / DRIVER).chmod((tree / DRIVER).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        out = (tree / DRIVER).read_text()
        assert "T7000_PCIE_MSI_VECTOR" not in out, "old constant names must be gone"
        # Compile + run the real patched driver in the host harness: the trace must equal golden.
        trace = seq.normalize(seq.run_trace(tree / DRIVER))
        golden = seq.normalize(seq.GOLDEN.read_text())
        assert trace == golden, "0056 changed the register read/write/delay sequence"
        seq.check_invariants(seq.run_trace(tree / DRIVER))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-clean-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_clean_source:
        check_apply(args.j81_clean_source)
    print("PASS" + (" (text contract + zero-fuzz apply + host trace identical to golden)" if args.j81_clean_source else " (text contract only)"))


if __name__ == "__main__":
    main()
