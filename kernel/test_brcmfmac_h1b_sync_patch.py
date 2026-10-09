#!/usr/bin/env python3
"""Patch 0083 (brcmfmac msgbuf: marker lines with sleeps in the attach path, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0083-brcmfmac-h1b-sync-sleeps.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    assert "module_param_named(h1b_sync_ms, h1b_sync_ms, uint, 0444);" in plus
    assert "if (!h1b_sync_ms)\n\t\treturn;" in plus and "msleep(h1b_sync_ms);" in plus
    for step in ("msgbuf attach entered", "ioctl buffer mapped", "before feeding", "rx data buffers posted", "event buffers posted",
                 "ioctl response buffers posted", "query ioctl about to be posted", "query ioctl posted, waiting for the response"):
        assert f'h1b_sync("{step}");' in plus, step
    # Sleeping is only legal in process context: none of the sync calls sit inside the spinlocked ring code (no commonring lock text added).
    assert "spin_lock" not in code and "commonring_lock" not in code
    for forbidden in ("writel", "iowrite", "write_reg32", "write_tcm", "gpiod"):
        assert forbidden not in code, forbidden
    print("PASS")


if __name__ == "__main__":
    main()
