#!/usr/bin/env python3
"""Patch 0059 (read-only +0x168 diagnostic, TEST kernels only): contract, apply, host trace.

Usage: python3 kernel/test_pcie_diag_msiaddr_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation. With it: zero-fuzz apply; with the Kconfig
option off the register trace equals the 0053 golden; with it on, the trace is the golden plus
exactly one read of +0x168 and no extra write, delay or other access.
"""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0059-pcie-apple-t7000-diag-msiaddr-readonly.patch"
FILES = ("drivers/pci/controller/Kconfig", "drivers/pci/controller/pcie-apple-t7000.c")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert touched == list(FILES), touched
    plus = added(text)
    for fragment in ("config PCIE_APPLE_T7000_DIAG_MSIADDR", "depends on PCIE_APPLE_T7000",
                     "IS_ENABLED(CONFIG_PCIE_APPLE_T7000_DIAG_MSIADDR)", "u32 msiaddr = readl(ctrl + T7000_PCIE_PORT_MSIADDR_DIAG);"):
        assert fragment in plus, fragment
    code = "\n".join(l for l in plus.splitlines() if not l.lstrip().startswith(("/*", "*", "//")))
    for forbidden in ("writel", "writew", "writeb", "t7000_pcie_write32", "gpiod_", "pmu"):
        assert forbidden not in code, forbidden


def reads_writes(trace):
    return [l for l in trace.splitlines() if l.split()[:1] and l.split()[0][:1] in "RW" and l.split()[0][1:].isdigit()]


def check_apply(source):
    spec = importlib.util.spec_from_file_location("seq", HERE / "test_pcie_write_sequence.py")
    seq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq)
    with tempfile.TemporaryDirectory(prefix="pcie-p59-") as tmp:
        tree = Path(tmp)
        for rel in FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        driver = tree / FILES[1]
        golden = seq.normalize(seq.GOLDEN.read_text())
        off = seq.normalize(seq.run_trace(driver))
        assert off == golden, "diagnostic off must not change the trace"
        on = seq.normalize(seq.run_trace(driver, defines=("CONFIG_PCIE_APPLE_T7000_DIAG_MSIADDR=1",)))
        # One extra read per harness scenario (zeros/ones, with and without REG_ON).
        g, o = golden.splitlines(), on.splitlines()
        extra = [l for l in o if "win3+0x00168" in l]
        n = golden.count("== scenario")
        assert len(o) == len(g) + n and len(extra) == n and all(l.startswith("R32") for l in extra), extra
        assert [l for l in o if "win3+0x00168" not in l] == g, "nothing else may change"
        assert not any(l.startswith("W") and "168" in l for l in on.splitlines()), "+0x168 must never be written"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply + host trace)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
