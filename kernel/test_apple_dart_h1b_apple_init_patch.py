#!/usr/bin/env python3
"""Patch 0085 (apple-dart: Apple start-up order, TEST kernels only). Text-contract test; the real compile is the Nix build."""
from pathlib import Path

P = Path(__file__).parent / "patches" / "0085-apple-dart-h1b-apple-init-order.patch"


def main():
    text = P.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == ["drivers/iommu/apple-dart.c"]
    assert not [l for l in text.splitlines() if l.startswith("-") and not l.startswith("---")], "patch must only add lines"
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    assert "module_param_named(h1b_apple_init, apple_dart_h1b_apple_init, uint, 0444);" in plus
    assert '"602002000."' in plus and "DART_S5L8960X" in plus, "must be limited to the PCIe DART"
    for const in ("0x0020ffff", "0x00000100", "0x000e0303", "0x24", "0x20", "0x30"):
        assert const in plus, const
    assert plus.count("#ifdef CONFIG_APPLE_DART_H1B_DIAG") >= 3
    # the error-reflector write precedes the first readl of hw_reset
    assert plus.index("writel(H1B_APCIE1_ERROR_REFLECTOR") < plus.index("config = readl(dart->regs + dart->hw->lock);") if "config = readl(dart->regs + dart->hw->lock);" in plus else True
    print("PASS")


if __name__ == "__main__":
    main()
