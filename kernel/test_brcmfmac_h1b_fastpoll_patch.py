#!/usr/bin/env python3
"""Patch 0077 (brcmfmac H1B: fast firmware-console poll thread, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0077-brcmfmac-h1b-fast-console-poll.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    for forbidden in ("write_reg32", "write_tcm", "pci_write_config", "writel", "iowrite", "ring_bell", "gpiod", "select_core"):
        assert forbidden not in code, forbidden
    assert "module_param_named(h1b_fast_poll_us, h1b_fast_poll_us, uint, 0444)" in plus
    # Only the existing read-only console reader runs in the thread, for at most 3 s, and the thread is stopped on release.
    assert code.count("brcmf_pcie_bus_console_read(devinfo, true)") == 1
    assert "time_before(jiffies, end)" in plus and "end = jiffies + 3 * HZ" in plus
    assert "kthread_stop(h1b_poll_task);" in plus
    # Default (parameter 0) keeps the 100 ms timer path: the fast path returns early only when the parameter is set.
    assert "if (h1b_fast_poll_us) {" in plus
    print("PASS")


if __name__ == "__main__":
    main()
