#!/usr/bin/env python3
"""Guard patch 0053 (DLLLA link wait): read-only, narrow, and it really applies.

Usage: python3 kernel/test_pcie_link_wait_dllla_patch.py [--j81-reg-on-source DIR]

DIR is the exact source tree of the 0052 kernel derivation (patches 0001-0011,
0016, 0040-0045 and 0052 applied). Without it only the text contract is checked.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

PATCH = Path(__file__).with_name("patches") / "0053-pcie-apple-t7000-link-wait-dllla.patch"
TARGET = "drivers/pci/controller/pcie-apple-t7000.c"


def added(text):
    return [l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++")]


def removed(text):
    return [l[1:] for l in text.splitlines() if l.startswith("-") and not l.startswith("---")]


def check_text(text):
    plus, minus = "\n".join(added(text)), "\n".join(removed(text))
    # Strictly read-only: no write of any kind in the patch, added or context.
    for call in ("writel", "writew", "writeb", "regmap_write", "i2c_", "gpiod_set", "of_find_compatible_node"):
        assert call not in text, call
    assert "0x0402" not in text and "luetooth" not in plus.replace("Bluetooth work", "")
    # The old undecoded bit-6 success logic is gone and the DLLLA wait replaces it.
    assert "T7000_PCIE_LINK_UP_BIT" in minus and "T7000_PCIE_LINK_UP_BIT" not in plus
    assert "t7000_pcie_wait_link_up(" in minus and "t7000_pcie_wait_link_up(" not in plus
    for fragment in ("T7000_PCIE_LNKSTA_OFFSET\t0x12", "T7000_PCIE_LNKSTA_DLLLA\tBIT(13)",
                     "T7000_PCIE_LNKCAP_OFFSET\t0x0c", "T7000_PCIE_LNKCAP_DLLLARC\tBIT(20)",
                     "T7000_PCIE_LINK_ACTIVE_TIMEOUT_MS\t1000", "t7000_pcie_find_express_cap",
                     "t7000_pcie_wait_link_active", "T7000_PCIE_ROOT_PORT_ECAM_OFFSET"):
        assert fragment in plus, fragment
    # Not fatal on timeout (behaviour kept), and the raw words stay as an undecoded log.
    assert "dev_warn" in plus and "undecoded" in plus
    assert "return -E" not in plus.split("t7000_pcie_wait_link_active", 1)[1].split("static void t7000_pcie_rmw", 1)[0]
    # Gen1 target speed handling is untouched.
    assert "LNKCTL2" not in "\n".join(l for l in removed(text) if "writew" in l)


def check_apply(source):
    source = Path(source).resolve()
    src_file = source / TARGET
    assert src_file.is_file(), src_file
    with tempfile.TemporaryDirectory(prefix="pcie-dllla-") as tmp:
        tree = Path(tmp)
        target = tree / TARGET
        target.parent.mkdir(parents=True)
        shutil.copy2(src_file, target)
        target.chmod(target.stat().st_mode | 0o200)
        result = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)],
                                cwd=tree, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        out = target.read_text()
    assert "T7000_PCIE_LINK_UP_BIT" not in out and "t7000_pcie_wait_link_up" not in out
    # Exactly the Gen1 write that existed before, still once, now via the shared lookup.
    assert len(re.findall(r"writew\(new, dev1 \+ cap_ptr \+ T7000_PCIE_LNKCTL2_OFFSET\)", out)) == 1
    assert "cap_ptr = t7000_pcie_find_express_cap(dev1);" in out
    wait = out.split("static void t7000_pcie_wait_link_active", 1)[1].split("static void t7000_pcie_rmw", 1)[0]
    assert "BIT(6)" not in wait and "write" not in wait
    assert "t7000_pcie_wait_link_active(dev, cfg, ctrl);" in out
    assert out.index("t7000_pcie_find_express_cap(void") < out.index("t7000_pcie_set_max_link_speed(struct")
    # REG_ON from 0052 and the other recovered writes are still present.
    assert "t7000_pcie_assert_j81_wifi_reg_on" in out and "T7000_PCIE_J81_REG_ON_CONFIG\t0x0403" in out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-reg-on-source", type=Path)
    args = parser.parse_args()
    check_text(PATCH.read_text())
    if args.j81_reg_on_source:
        check_apply(args.j81_reg_on_source)
    print("PASS" + (" (text contract + zero-fuzz apply)" if args.j81_reg_on_source else " (text contract only)"))


if __name__ == "__main__":
    main()
