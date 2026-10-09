#!/usr/bin/env python3
"""Patch 0084 (brcmfmac pcie: h1b_no_bell skips the H2D doorbell, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0084-brcmfmac-h1b-skip-doorbell.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    assert "module_param_named(h1b_no_bell, h1b_no_bell, uint, 0444);" in plus
    assert "#ifdef CONFIG_BRCMFMAC_PCIE_H1B_DIAG" in plus and "if (h1b_no_bell) {" in plus and "return 0;" in plus
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    for forbidden in ("writel", "iowrite", "write_reg32", "write_tcm", "gpiod"):
        assert forbidden not in code, forbidden
    assert not [l for l in text.splitlines() if l.startswith("-") and not l.startswith("---")], "patch must only add lines"
    print("PASS")


if __name__ == "__main__":
    main()
