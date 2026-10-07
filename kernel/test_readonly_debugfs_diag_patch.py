#!/usr/bin/env python3
"""Patch 0066 (read-only debugfs diagnostics for the DART and the T7000 port, TEST kernels only).

Usage: python3 kernel/test_readonly_debugfs_diag_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation. The patch adds two opt-in Kconfig options and
two register dumps exposed with debugfs_create_regset32 (mode 0444): no write of any kind. With the
options off the PCIe driver's register/delay trace must equal the 0053 golden (the host harness);
the apple-dart changes compile only in the Nix kernel build.
"""
import argparse
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0066-readonly-debugfs-diag-dart-and-t7000-port.patch"
FILES = ("drivers/iommu/Kconfig", "drivers/iommu/apple-dart.c", "drivers/pci/controller/Kconfig",
         "drivers/pci/controller/pcie-apple-t7000.c")
PCIE = FILES[3]


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == list(FILES)
    plus = added(text)
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    for sym in ("config APPLE_DART_H1B_DIAG", "config PCIE_APPLE_T7000_DEBUGFS_DIAG",
                "#ifdef CONFIG_APPLE_DART_H1B_DIAG", "#ifdef CONFIG_PCIE_APPLE_T7000_DEBUGFS_DIAG"):
        assert sym in plus, sym
    assert "depends on APPLE_DART && DEBUG_FS" in plus and "depends on PCIE_APPLE_T7000 && DEBUG_FS" in plus
    # Read-only: files are 0444 regsets; nothing writes a register, clears a flag or changes state.
    for forbidden in ("writel", "writeb", "writew", "iowrite", "t7000_pcie_write32", "debugfs_create_file(",
                      "0644", "0666", "0222", "request_irq", "free_irq", "mutex", "iommu_"):
        assert forbidden not in code, forbidden
    assert code.count("debugfs_create_regset32(") == 2 and code.count('0444') == 2
    # The DART dump is S5L8960X only and the dump calls sit after successful init.
    assert "dart->hw->type != DART_S5L8960X" in code
    assert code.count("apple_dart_h1b_debugfs(dart);") == 1 and code.count("t7000_pcie_debugfs(dev, ctrl);") == 1
    # The port dump lists only registers earlier hardware tests already read.
    offs = set(re.findall(r"\{ \"[a-z_0-9x]+\", (0x[0-9a-f]+) \}", plus))
    assert offs == {"0x080", "0x088", "0x08c", "0x100", "0x104", "0x124", "0x128", "0x168"}, offs


def check_apply(source):
    spec = importlib.util.spec_from_file_location("seq", HERE / "test_pcie_write_sequence.py")
    seq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq)
    with tempfile.TemporaryDirectory(prefix="dbg-p66-") as tmp:
        tree = Path(tmp)
        for rel in FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        golden = seq.normalize(seq.GOLDEN.read_text())
        assert seq.normalize(seq.run_trace(tree / PCIE)) == golden, "option off must not change the PCIe trace"
        dart = (tree / FILES[1]).read_text()
        pcie = (tree / PCIE).read_text()
        # Helpers are defined before use (the 0063 lesson).
        assert dart.index("static void apple_dart_h1b_debugfs") < dart.index("apple_dart_h1b_debugfs(dart);")
        assert pcie.index("static void t7000_pcie_debugfs") < pcie.index("t7000_pcie_debugfs(dev, ctrl);")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply + trace unchanged with the options off)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
