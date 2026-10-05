#!/usr/bin/env python3
"""Guard the J81 board-bound REG_ON patch's deliberately narrow contract."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


PATCH = Path(__file__).with_name("patches") / "0052-pcie-apple-t7000-j81-reg-on.patch"
ROOT = PATCH.parents[2]
TEST_PATCH = PATCH.with_name("0050-pcie-apple-t7000-reg-on-test.patch")


def assert_zero_fuzz_apply(reg_on_test_source: Path) -> None:
    """Apply 0052 to the exact Stage-5F source recovered from the 0050 output."""
    source = reg_on_test_source.resolve()
    needed = (
        "drivers/pci/controller/pcie-apple-t7000.c",
        "arch/arm64/boot/dts/apple/t7001-air2.dtsi",
    )
    for relative in needed:
        assert (source / relative).is_file(), relative

    with tempfile.TemporaryDirectory(prefix="pcie-j81-reg-on-") as temporary:
        tree = Path(temporary)
        for relative in needed:
            target = tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
            target.chmod(target.stat().st_mode | 0o200)
        (tree / "Documentation/devicetree/bindings/pci").mkdir(parents=True)

        reverse = subprocess.run(
            ["patch", "--batch", "--fuzz=0", "-R", "-p1", "-i", str(TEST_PATCH)],
            cwd=tree, capture_output=True, text=True,
        )
        assert reverse.returncode == 0, reverse.stdout + reverse.stderr
        apply = subprocess.run(
            ["patch", "--batch", "--fuzz=0", "--dry-run", "-p1", "-i", str(PATCH)],
            cwd=tree, capture_output=True, text=True,
        )
        assert apply.returncode == 0, apply.stdout + apply.stderr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reg-on-test-source", type=Path,
        help="exact source tree built by the 0050 REG_ON test derivation",
    )
    args = parser.parse_args()
    text = PATCH.read_text()
    required = (
        '"apple,reg-on-pmic"',
        "d2207: pmic@3c",
        "apple,reg-on-pmic = <&d2207>;",
        "of_parse_phandle",
        "T7000_PCIE_J81_REG_ON_CONFIG\t0x0403",
        "(old & 0x1d) | 0x02",
        "readback != value",
        "T7000_PCIE_J81_REG_ON_DELAY_MS\t100",
        "failed to assert declared J81 Wi-Fi REG_ON",
    )
    for fragment in required:
        assert fragment in text, fragment
    assert "of_find_compatible_node" not in text
    assert "of_find_property" not in text
    assert "of_property_present" in text
    assert "0x0402" not in text
    assert "Bluetooth GPIO2 register" in text

    flake = (ROOT / "flake.nix").read_text()
    assert "hoolockPcieJ81RegOnKernel" in flake
    payload = flake.split("m1n1-hoolock-pcie-j81-reg-on =", 1)[1]
    payload = payload.split("m1n1-hoolock-pcie-link-wait-write-test =", 1)[0]
    assert "hoolockPcieJ81RegOnKernel" in payload
    assert "btattach" not in payload

    if args.reg_on_test_source:
        assert_zero_fuzz_apply(args.reg_on_test_source)


if __name__ == "__main__":
    main()
