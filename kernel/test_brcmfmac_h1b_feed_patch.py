#!/usr/bin/env python3
"""Patch 0082 (brcmfmac msgbuf: split the buffer feeding at attach, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0082-brcmfmac-h1b-split-buffer-feeding.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/net/wireless/broadcom/brcm80211/brcmfmac/msgbuf.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    assert "static unsigned int h1b_feed = 7;" in plus and "module_param_named(h1b_feed, h1b_feed, uint, 0444);" in plus
    assert "module_param_named(h1b_rxpost, h1b_rxpost, uint, 0444);" in plus and "#include <linux/module.h>" in plus
    # Default (mask 7, rxpost 0) leaves the stock sequence: data fill loop, event post, ioctl-response post, in that order.
    assert plus.index("if (h1b_feed & 1) {") < plus.index("if (h1b_feed & 2) {") < plus.index("if (h1b_feed & 4) {")
    assert "if (h1b_rxpost && h1b_rxpost < msgbuf->max_rxbufpost)" in plus
    for call in ("brcmf_msgbuf_rxbuf_data_fill(msgbuf);", "brcmf_msgbuf_rxbuf_event_post(msgbuf);", "brcmf_msgbuf_rxbuf_ioctlresp_post(msgbuf);"):
        assert call in plus, call
    for forbidden in ("writel", "iowrite", "write_reg32", "write_tcm", "gpiod"):
        assert forbidden not in code, forbidden
    print("PASS")


if __name__ == "__main__":
    main()
