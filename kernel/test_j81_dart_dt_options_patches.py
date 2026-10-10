#!/usr/bin/env python3
"""Patches 0089 (apple-dart/io-pgtable-dart: J81 PCIe DART options from the device tree, leaf |3 default) and 0090 (DT nodes). Text-contract test; the real compile is the Nix build."""
from pathlib import Path

D = Path(__file__).parent / "patches"


def plus(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def main():
    t89 = (D / "0089-apple-dart-j81-options-from-device-tree.patch").read_text()
    files = [l.split(" b/")[1] for l in t89.splitlines() if l.startswith("diff --git")]
    assert files == ["drivers/iommu/apple-dart.c", "drivers/iommu/io-pgtable-dart.c"], files
    p = plus(t89)
    for prop in ("apple,ios-pte", "apple,pci-alias", "apple,error-reflector", "apple,fetch-config", "apple,diag-config"):
        assert f'"{prop}"' in p, prop
    assert "static unsigned int ios_leaf_bits = 1;" in p, "leaf |3 must be the default"
    assert "writel(dart->error_reflector" in p
    # The error reflector is written before the first register read of hw_reset.
    seg = p[p.index("if (dart->has_apple_init)\n\t\twritel(dart->error_reflector"):]
    assert "CONFIG_APPLE_DART_H1B_DIAG" not in p.split("static void apple_dart_parse_apple_init")[0].split("APPLE_DART_S5L8960X_DIAG_CONFIG")[0][-200:]
    assert "H1B_APCIE1" not in p and "apple_dart_h1b_is_apcie1" not in p
    # Only the S5L8960X DART parses the options.
    assert "if (dart->hw->type != DART_S5L8960X)\n\t\treturn;" in p
    t90 = (D / "0090-t7001-air2-pcie-dart-options-and-wifi-node.patch").read_text()
    files = [l.split(" b/")[1] for l in t90.splitlines() if l.startswith("diff --git")]
    assert files == ["arch/arm64/boot/dts/apple/t7001.dtsi", "arch/arm64/boot/dts/apple/t7001-air2.dtsi"], files
    q = plus(t90)
    assert "wifi0 = &wifi0;" in q and "wifi0: network@0,0 {" in q
    assert 'compatible = "pci14e4,43a3";' in q and "reg = <0x10000 0x0 0x0 0x0 0x0>;" in q
    assert "local-mac-address = [00 00 00 00 00 00];" in q, "placeholder only; real MACs never go in Git"
    assert "pci@1,0 {" in q and "reg = <0x800 0x0 0x0 0x0 0x0>;" in q
    assert "&dart_apcie1 {" in q and "apple,error-reflector = <0x0020ffff>;" in q
    import re
    assert not re.search(r"local-mac-address = \[(?!00 00 00 00 00 00)", q), "no real MAC may be in the patch"
    print("PASS")


if __name__ == "__main__":
    main()
