#!/usr/bin/env python3
"""Patch 0079 (brcmfmac H1B: TCM-indices option and a doorbell-only test, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0079-brcmfmac-h1b-tcm-indices-and-bell-only.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    # The only register write is the one doorbell write, and only under h1b_bell_only.
    assert code.count("brcmf_pcie_write_reg32(") == 1 and "h2d_mailbox_0, 1);" in plus
    for forbidden in ("write_tcm", "pci_write_config", "writel", "iowrite", "gpiod", "select_core", "ring_bell"):
        assert forbidden not in code, forbidden
    assert "module_param_named(h1b_tcm_idx, h1b_tcm_idx, uint, 0444)" in plus
    assert "module_param_named(h1b_bell_only, h1b_bell_only, uint, 0444)" in plus
    assert "if (!h1b_bell_only)\n\t\treturn;" in plus
    # Default behaviour unchanged: the stock DMA-index branch is only skipped when the option is on.
    assert "if (h1b_tcm_idx_forced()) {" in plus and "} else if (shared->flags & BRCMF_PCIE_SHARED_DMA_INDEX) {" in plus
    assert "static inline bool h1b_tcm_idx_forced(void) { return false; }" in plus
    # The doorbell-only test runs right after the last setup pause and before brcmf_attach().
    assert "h1b_bell_only_test(devinfo);" in plus
    print("PASS")


if __name__ == "__main__":
    main()
