#!/usr/bin/env python3
"""Patch 0065 (brcmfmac PCIe H1B diagnostics, TEST kernels only): contract and zero-fuzz apply.

Usage: python3 kernel/test_brcmfmac_h1b_diag_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation (brcmfmac is unpatched there). The diagnostics
must be read-only and confined to one Kconfig option: no writes, no firmware RAM dump, only ring
headers (32 bytes of two control rings) and the 8-byte d2h scratch word are ever printed. The real
compile gate is the Nix kernel build.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0065-brcmfmac-pcie-h1b-diag.patch"
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
FILES = (B + "Kconfig", B + "pcie.c")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == list(FILES)
    plus = added(text)
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)          # string literals (log text) are not code
    assert "config BRCMFMAC_PCIE_H1B_DIAG" in plus and "depends on BRCMFMAC_PCIE" in plus
    assert "#ifdef CONFIG_BRCMFMAC_PCIE_H1B_DIAG" in plus and "#else" in plus and "#endif" in plus
    # Read-only: no register/TCM/config/memory writes, no DMA sync, no firmware RAM access, no bus-master changes.
    for forbidden in ("brcmf_pcie_write_", "brcmf_pcie_copy_dev_tomem", "writel", "iowrite", "pci_write_config",
                      "pci_set_master", "memcpy", "memset", "dma_sync", "dma_map", "dma_unmap", "write_ptr",
                      "ring_bell", "tcm", "request_irq", "free_irq", "pci_enable_msi", "pci_disable"):
        assert forbidden not in code.replace("devinfo->shared.tcm_base_address", ""), forbidden
    # Only protocol headers and the 8-byte scratch word are printed: 32/8 byte dumps, nothing else.
    dumps = re.findall(r"%\*phN\\n\",\s*(?:i,\s*)?(\d+),", plus)
    assert sorted(dumps) == ["32", "8"], dumps
    # Hooks sit at the intended sites and nothing is hooked into the data path.
    for hook in ("h1b_isr_note(devinfo, irq, status);", 'h1b_log_msi(devinfo, "after pci_enable_msi");',
                 'h1b_log_msi(devinfo, "after request_irq");', 'h1b_dump_rings(devinfo, "firmware declared dead");',
                 'h1b_log_dma(devinfo, "ring"', 'h1b_log_dma(devinfo, "scratch"', 'h1b_log_dma(devinfo, "ringupd"'):
        assert hook in plus, hook
    # The isr hook is bounded (first 32 interrupts only) so it cannot flood the log.
    assert "if (n <= 32)" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p65-") as tmp:
        tree = Path(tmp)
        for rel in FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        src = (tree / FILES[1]).read_text()
        # Every helper is defined before its first use (the 0063 lesson).
        for name in ("h1b_log_domain", "h1b_log_dma", "h1b_log_msi", "h1b_isr_note", "h1b_dump_rings"):
            first = src.index(name + "(")
            assert src.rindex("static", 0, first) > src.rindex("\n\n", 0, first) - 400 or "static" in src[first - 40:first], name
            assert src.index("static void " + name) <= first or src.index("static inline void " + name) <= first, name
        assert src.count("#ifdef CONFIG_BRCMFMAC_PCIE_H1B_DIAG") == 1


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
