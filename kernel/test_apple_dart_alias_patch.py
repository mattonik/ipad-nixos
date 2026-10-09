#!/usr/bin/env python3
"""Patch 0080 (apple-dart: optional second mapping of PCI-window pages at the raw index, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0080-apple-dart-pci-alias-raw-index-mapping.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/iommu/apple-dart.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    assert "static int apple_dart_pci_alias;" in plus and "module_param_named(pci_alias, apple_dart_pci_alias, int, 0444);" in plus
    assert "u64 alias_mask;" in plus
    # Off by default: the alias mask is only set when the parameter is on and a PCI window with the rebase model is in use.
    assert "if (apple_dart_pci_alias && cfg->pci_window) {" in plus and "dart_domain->alias_mask = DMA_BIT_MASK(pgtbl_cfg.ias);" in plus
    # Every map is mirrored and every unmap is mirrored, with the alias only when enabled.
    assert "dart_domain->alias_mask && *mapped" in plus and "unmapped && dart_domain->alias_mask" in plus
    assert "domain->dev" not in code, "struct iommu_domain has no dev member"
    for forbidden in ("writel", "iowrite", "write_reg32", "gpiod"):
        assert forbidden not in code, forbidden
    # The param is defined before its first use (finalize_domain comes after map_pages in the file).
    assert plus.index("static int apple_dart_pci_alias;") < plus.index("if (apple_dart_pci_alias && cfg->pci_window)")
    print("PASS")


if __name__ == "__main__":
    main()
