#!/usr/bin/env python3
"""Patch 0073 (brcmfmac H1B: RAM snapshot/diff, ARM state, gated ROM reads, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_romgate_patch.py [--j81-msi-source DIR]
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
NAMES = ("0065-brcmfmac-pcie-h1b-diag.patch", "0066-readonly-debugfs-diag-dart-and-t7000-port.patch",
         "0067-j81-wifi-deep-sleep-and-device-wake-toggles.patch", "0068-brcmfmac-h1b-console-poll-and-shared-state.patch",
         "0069-brcmfmac-h1b-chipcommon-gpio-snapshot.patch", "0070-brcmfmac-h1b-apple-shared-memory-parity.patch",
         "0071-brcmfmac-h1b-readonly-query-interface.patch", "0072-brcmfmac-h1b-ring-ids-and-safe-register-reads.patch",
         "0073-brcmfmac-h1b-query-snapshot-arm-and-gated-rom.patch")
PATCHES = [HERE / "patches" / n for n in NAMES]
P73 = PATCHES[-1]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def strip(plus):
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)


def check_text():
    text = P73.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
    code = strip(plus)
    for forbidden in ("write_reg32", "write_tcm", "write_ptr", "write_ram", "pci_write_config", "writel", "iowrite", "memcpy_toio",
                      "ring_bell", "send_mb_data", "request_irq", "free_irq", "msleep", "udelay", "gpiod"):
        assert forbidden not in code, forbidden
    # tcm: absolute ARM addresses inside [rambase, rambase + ramsize).
    assert "off < devinfo->ci->rambase" in plus and "ramsize - (off - devinfo->ci->rambase)" in plus
    # ROM reads: locked until "unlock rom", need the hold, bounded, below the RAM base and inside BAR2, logged first.
    rom = code[code.index("unlock rom") if "unlock rom" in code else 0:]
    unlock = plus[plus.index('!strcmp(cmd, "unlock rom")'):plus.index('sscanf(cmd, "rom %i %i"')]
    assert "!h1b_hold_mask" in unlock and "h1b_rom_unlocked = true;" in unlock
    read = plus[plus.index('sscanf(cmd, "rom %i %i"'):]
    read = read[:read.index("h1b_q_tcm(devinfo, \"rom\"")]
    assert read.index("!h1b_rom_unlocked") < read.index("off >= devinfo->ci->rambase")
    assert "len > H1B_Q_ROM_MAX" in read and "(u64)off + len > bar2" in read and "len > devinfo->ci->rambase - off" in read
    assert read.index("dev_warn(") > read.index("(u64)off + len > bar2")
    assert "#define H1B_Q_ROM_MAX\t\t0x1000" in plus
    assert "static bool h1b_rom_unlocked;" in plus and "= false" not in plus.replace("h1b_rom_unlocked = true", "")
    # arm / snapshot: hold needed for the window-moving core state; snapshot is a plain RAM copy.
    arm = plus[plus.index('!strcmp(cmd, "arm")'):plus.index('!strcmp(cmd, "unlock rom")')]
    assert "!h1b_hold_mask" in arm
    fn = code[code.index("static void h1b_q_arm"):]
    assert fn.index("disable_irq(") < fn.index("brcmf_chip_iscoreup") < fn.index("brcmf_pcie_select_core(devinfo, BCMA_CORE_PCIE2)") < fn.index("enable_irq(")
    assert "strim(cmd)" in plus
    assert "H1B_Q_DIFF_LINES\t400" in plus


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p73-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        run = src.index("static void h1b_q_run")
        for fn in ("static u32 *h1b_q_read_ram(", "static void h1b_q_snap(", "static void h1b_q_diff(", "static void h1b_q_arm("):
            assert src.index(fn) < run, fn
        assert src.index("brcmf_pcie_copy_dev_tomem(struct") < src.index("static u32 *h1b_q_read_ram(")
        assert src.index("static void h1b_q_tcm(") < run
        assert "#include <linux/mm.h>" in src or "kvmalloc" in src  # kvmalloc comes in via slab.h/mm.h pulled by existing includes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0072)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
