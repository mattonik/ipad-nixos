#!/usr/bin/env python3
"""Patch 0076 (apple-dart: boot-time override of the PCI IOVA indexing model, TEST kernels only).

Usage: python3 kernel/test_apple_dart_rebase_override_patch.py

apple_dart.pci_rebase=1 -> model A (rebased), =0 -> model B (raw), -1 (default) -> as the device tree says. Only affects PCI devices that
have an apple,iova-window (the Wi-Fi endpoint). Text-contract test; the real compile is the Nix build.
"""
from pathlib import Path

P = Path(__file__).parent / "patches" / "0076-apple-dart-pci-rebase-boot-override.patch"


def main():
    text = P.read_text()
    files = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert files == ["drivers/iommu/apple-dart.c", "drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"], files
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    assert "static int apple_dart_pci_rebase = -1;" in plus
    assert "module_param_named(pci_rebase, apple_dart_pci_rebase, int, 0444);" in plus
    # Only overrides when a window user is being configured and the argument is 0 or 1; default leaves the DT choice untouched.
    assert "if (apple_dart_pci_rebase >= 0) {" in plus and "no_rebase = !apple_dart_pci_rebase;" in plus
    ctx = text.index("no_rebase = !of_property_read_bool") if "no_rebase = !of_property_read_bool" in text else -1
    assert ctx > 0 and ctx < text.index("if (apple_dart_pci_rebase >= 0) {")
    assert 'h1b_log_dma(devinfo, "idxbuf", devinfo->idxbuf_dmahandle, bufsz);' in plus
    for forbidden in ("write_reg32", "write_tcm", "pci_write_config", "writel", "iowrite", "ring_bell", "gpiod"):
        assert forbidden not in plus, forbidden
    print("PASS")


if __name__ == "__main__":
    main()
