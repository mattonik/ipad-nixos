#!/usr/bin/env python3
"""Patch 0078 (brcmfmac H1B: pauses between the phases of brcmf_pcie_setup, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0078-brcmfmac-h1b-setup-step-pauses.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    for forbidden in ("write_reg32", "write_tcm", "read_reg32", "read_tcm", "pci_write_config", "writel", "iowrite", "ring_bell", "gpiod", "select_core"):
        assert forbidden not in code, forbidden   # the pauses touch no hardware at all
    assert "module_param_named(h1b_step_s, h1b_step_s, uint, 0444)" in plus
    assert "if (!h1b_step_s)" in plus and "ssleep(h1b_step_s);" in plus
    for phase in ("firmware download and start", "ring buffers", "scratch buffers", "interrupt request", "msgbuf hookup, before attach"):
        assert f'h1b_step(devinfo, "{phase}");' in plus, phase
    # The firmware-start pause comes before the state change and the ring setup; the last one right before brcmf_attach().
    assert plus.index('"firmware download and start"') < plus.index('"ring buffers"') < plus.index('"scratch buffers"') < plus.index('"interrupt request"') < plus.index('"msgbuf hookup, before attach"')
    assert "static inline void h1b_step(struct brcmf_pciedev_info *devinfo, const char *what) { }" in plus
    print("PASS")


if __name__ == "__main__":
    main()
