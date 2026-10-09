#!/usr/bin/env python3
"""Patch 0081 (apple-dart / io-pgtable-dart: iOS-style S5L8960X page-table entries, TEST kernels only). Text-contract test; the real compile is the Nix build.

Evidence (iOS 8.1 AppleS5L8960XDART decompile): directory entries (paddr & 0xfffffff000) | 3, leaf entries (pfn << 12) | 2 (valid bit 1), TTBR = pfn | 0x80000000.
Linux's generic DART1 format uses bit 0 as the valid bit and sets subpage fields at 51:40.
"""
from pathlib import Path
import re

P = Path(__file__).parent / "patches" / "0081-apple-dart-s5l8960x-ios-pte-format.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [
        "drivers/iommu/apple-dart.c", "drivers/iommu/io-pgtable-dart.c", "include/linux/io-pgtable.h"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', re.sub(r"/\*.*?\*/", "", plus, flags=re.S))
    assert "module_param_named(ios_pte, apple_dart_ios_pte, int, 0444);" in plus and "static int apple_dart_ios_pte;" in plus
    # Off by default and only for the S5L8960X DART.
    assert "if (apple_dart_ios_pte && dart->hw->type == DART_S5L8960X) {" in plus and "pgtbl_cfg.apple_dart_cfg.ios_pte = true;" in plus
    assert "bool ios_pte;" in plus and "data->ios_pte = cfg->apple_dart_cfg.ios_pte;" in plus
    # The iOS format: leaf = 2, table = 3, no protection fields.
    assert "pte = BIT(1);" in plus and "(data->ios_pte ? 3 : APPLE_DART_PTE_VALID)" in plus
    assert "if (data->ios_pte)\n\t\treturn 0;" in plus
    assert "dart_iopte valid = data->ios_pte ? BIT(1) : APPLE_DART_PTE_VALID;" in plus
    # The stock path is untouched when the option is off.
    assert "pte |= FIELD_PREP(APPLE_DART_PTE_SUBPAGE_END, 0xfff);" in plus and "pte |= APPLE_DART_PTE_VALID;" in plus
    for forbidden in ("writel", "iowrite", "write_reg32", "gpiod"):
        assert forbidden not in code, forbidden
    # The param is defined before its use in apple_dart_finalize_domain (0080's block precedes map_pages and finalize).
    print("PASS")


if __name__ == "__main__":
    main()
