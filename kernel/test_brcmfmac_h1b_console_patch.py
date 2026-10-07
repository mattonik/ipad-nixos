#!/usr/bin/env python3
"""Patch 0068 (brcmfmac H1B: firmware console poll and shared-state snapshot, TEST kernels only).

Usage: python3 kernel/test_brcmfmac_h1b_console_patch.py [--j81-msi-source DIR]

Applies on top of 0065/0066/0067 (DIR = the 0057 kernel source tree). Read-only: it polls the firmware console
(TCM reads through the stock reader) every 100 ms for at most 30 ticks, and logs the shared structure, mailbox
words and registers at the failure snapshot. The only mutations are the poll timer and the driver's own console read index.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCHES = [HERE / "patches" / n for n in ("0065-brcmfmac-pcie-h1b-diag.patch",
                                           "0066-readonly-debugfs-diag-dart-and-t7000-port.patch",
                                           "0067-j81-wifi-deep-sleep-and-device-wake-toggles.patch",
                                           "0068-brcmfmac-h1b-console-poll-and-shared-state.patch")]
P68 = PATCHES[3]
B = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/"
SRC_FILES = (B + "pcie.c", B + "Kconfig", "drivers/pci/controller/pcie-apple-t7000.c", "drivers/pci/controller/Kconfig",
             "drivers/iommu/apple-dart.c", "drivers/iommu/Kconfig", "arch/arm64/boot/dts/apple/t7001.dtsi")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = P68.read_text()
    assert [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")] == [B + "pcie.c"]
    plus = added(text)
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    # Read-only: no register, TCM or config writes; the console is read with the stock reader.
    for forbidden in ("write_reg32", "write_tcm", "write_ptr", "pci_write_config", "writel", "iowrite", "ring_bell", "send_mb_data",
                      "request_irq", "free_irq", "msleep", "udelay", "gpiod", "memcpy"):
        assert forbidden not in code, forbidden
    assert code.count("brcmf_pcie_bus_console_read(devinfo, true)") == 2
    # Bounded: 100 ms period, 30 ticks, and the timer is always stopped when the irq is released.
    assert re.search(r"\+\+h1b_poll_ticks > 30\)", plus) and "msecs_to_jiffies(100)" in plus
    assert "+\th1b_console_poll_stop();" in text
    assert "h1b_console_poll_start(devinfo);" in plus and "timer_delete_sync(&h1b_console_timer)" in plus
    # The snapshot reads exactly the documented mailbox/shared items.
    for item in ("devinfo->shared.version", "devinfo->shared.flags", "htod_mb_data_addr", "dtoh_mb_data_addr",
                 "mailboxmask", "h2d_mailbox_0", "h2d_mailbox_1", "BRCMF_PCIE_REG_SBMBX"):
        assert item in plus, item


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="brcmfmac-p68-") as tmp:
        tree = Path(tmp)
        for rel in SRC_FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for p in PATCHES:
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(p)], cwd=tree, capture_output=True, text=True)
            assert r.returncode == 0, p.name + "\n" + r.stdout + r.stderr
        src = (tree / B / "pcie.c").read_text()
        # Definition before use; the stock console reader precedes the helpers; stubs exist for the option-off build.
        assert src.index("static void brcmf_pcie_bus_console_read") < src.index("static void h1b_console_tick")
        assert src.index("static void h1b_console_poll_start") < src.index("\th1b_console_poll_start(devinfo);")
        assert src.index("static void h1b_console_poll_stop") < src.index("\th1b_console_poll_stop();")
        assert "static inline void h1b_console_poll_start(struct brcmf_pciedev_info *devinfo) { }" in src
        assert src.count("static struct timer_list h1b_console_timer;") == 1
        # The timer is stopped at the very top of release_irq, before the early return for a never-allocated irq.
        rel = src[src.index("static void brcmf_pcie_release_irq"):]
        assert rel.index("h1b_console_poll_stop();") < rel.index("if (!devinfo->irq_allocated)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply on 0065-0067)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
