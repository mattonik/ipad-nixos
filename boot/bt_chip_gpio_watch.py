#!/usr/bin/env python3
"""Does the Wi-Fi chip's own GPIO block react when the Bluetooth control lines change? Three read-only ChipCommon snapshots on a HELD diagnostic Wi-Fi boot.

Research brief result (research/2026-10-11-bluetooth-lpo-wifi-dependency.md): the only remaining high-value test is to compare safe ChipCommon registers
(1) after the Wi-Fi firmware is up (baseline), (2) after BT_WAKE (AP GPIO 164) is asserted, (3) after the PMU power-enable (0x0402 0x09 -> 0x0b) is also asserted. A repeatable change in the chip's GPIO inputs
(its own `uart_wake_gpio=2`, UART/clock related pins) would tell us how the Bluetooth control lines are wired into the combo chip. Reads only the driver's safe ChipCommon block (0x58..0x6f) through the
debugfs query interface (patch 0071); no backplane write, no unknown-register read.

Requires a payload booted with brcmfmac.h1b_hold=1 (diagnostic kernel) and /tmp/bt/{pinpoke,i2ctransfer} on the iPad. Approved writes only (user, 2026-10-10: PMU 0x0402 0x09 -> 0x0b and AP GPIO 164 high,
each with readback and revert), restored in a finally block.

  boot/bt_chip_gpio_watch.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

DIR = "/sys/kernel/debug/brcmfmac-h1b"
# ChipCommon GPIO block: +0x58 pullup, +0x5c pulldown, +0x60 input, +0x64 output, +0x68 output-enable, +0x6c control (research/2026-10-07-wifi-h1b-modelA-run.md run 12)
NAMES = ["gpiopullup", "gpiopulldown", "gpioin", "gpioout", "gpioouten", "gpiocontrol"]


def sh(cmd, timeout=60):
    out, _ = run(cmd, timeout=timeout)
    return out.strip()


def snapshot():
    text = sh(f'mountpoint -q /sys/kernel/debug || mount -t debugfs none /sys/kernel/debug; echo "core cc 0x58 24" > {DIR}/query && cat {DIR}/result')
    # result lines look like "cc 00000058: 00000000 00000002 0000290e 00000000": take only the words after the address colon
    words = [int(w, 16) for line in text.splitlines() if ":" in line for w in re.findall(r"\b([0-9a-f]{8})\b", line.split(":", 1)[1])]
    return text, words[:6] if len(words) >= 6 else None


def show(label, words):
    print(f"{label:34s} " + " ".join(f"{n}={w:08x}" for n, w in zip(NAMES, words)), flush=True)


def diff(a, b):
    out = []
    for n, x, y in zip(NAMES, a, b):
        if x != y:
            out.append(f"{n}: {x:08x} -> {y:08x} (changed bits {x ^ y:08x})")
    return out or ["no change"]


def rd_pmu(hi, lo):
    return sh(f"cd /tmp/bt; ./i2ctransfer -f -y 0 w2@0x3c {hi} {lo} r1@0x3c 2>&1").splitlines()[-1].strip()


def rd_pin():
    m = re.search(r"reg (0x[0-9a-f]+)", sh("cd /tmp/bt; ./pinpoke read 164 2>&1"))
    return m.group(1) if m else None


def main():
    for tool in ("pinpoke", "i2ctransfer"):
        if "x" not in sh(f"ls -l /tmp/bt/{tool} 2>&1 | cut -c1-4"):
            sys.exit(f"/tmp/bt/{tool} is missing on the iPad")
    text, base = snapshot()
    if base is None:
        sys.exit(f"cannot read the ChipCommon block (is the payload booted with brcmfmac.h1b_hold=1?): {text[:200]!r}")
    orig_pin, g2, usb = rd_pin(), rd_pmu("0x04", "0x02"), rd_pmu("0x00", "0x10")
    print(f"baseline: pin164 {orig_pin}, 0x0402 {g2}, 0x0010 {usb}")
    if not orig_pin or g2 != "0x09" or usb != "0x00":
        sys.exit("unexpected baseline; nothing was written")
    show("1 baseline (firmware up)", base)
    _, again = snapshot()
    show("1b baseline again", again)
    print("   baseline stability:", diff(base, again))
    try:
        print(sh("cd /tmp/bt; ./pinpoke high 164"))
        sh("sleep 1")
        _, s2 = snapshot()
        show("2 after BT_WAKE high", s2)
        print("   vs baseline:", diff(base, s2))
        sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b")
        print("   0x0402 readback:", rd_pmu("0x04", "0x02"))
        for delay in (0.2, 2, 6):
            sh(f"sleep {delay}")
            _, s3 = snapshot()
            show(f"3 BT_WAKE + power-enable (+{delay}s)", s3)
            print("   vs baseline:", diff(base, s3))
    finally:
        print("--- RESTORE")
        sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09")
        sh(f"cd /tmp/bt; ./pinpoke restore 164 {orig_pin}")
        g2f, pinf, usbf = rd_pmu("0x04", "0x02"), rd_pin(), rd_pmu("0x00", "0x10")
        print(f"final: 0x0402 {g2f} (want 0x09), pin164 {pinf} (want {orig_pin}), 0x0010 {usbf}")
        _, s4 = snapshot()
        if s4:
            show("4 after restore", s4)
            print("   vs baseline:", diff(base, s4))
        if g2f != "0x09" or pinf != orig_pin:
            print("!!! RESTORE FAILED: check the registers by hand")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
