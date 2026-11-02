#!/usr/bin/env python3
"""UART3 pinmux A/B on the RUNNING iPad: move the Bluetooth UART's TX/RTS pads (AP GPIO 14, 32) from peripheral function 2 to 1, then repeat the HCI Reset probe.

Why (2026-11-02, research/2026-11-02-bt-uart3-pinmux-lead.md): our DT muxes GPIO 14/32 to function 2, picked from the ADT OIPG flags byte. BAT-4 proved that rule wrong on
UART5's GPIO34 (function 2: total silence; function 1: HDQ works). UART3's RX/CTS pads (15, 33) and the working UART0/UART4 pads read function 1, and Orchard's J81 DT muxes
all four UART3 pads to function 1. If the TX/RTS pads were never routed to UART3, no earlier probe at any rate could have reached the controller.

Writes, each read back and restored in a finally block:
  - AP GPIO 14 and 32: PERIPH field only, 2 -> 1 -> original (boot/pinpoke.c `func`, new for this test; needs the user's approval);
  - already-approved (2026-10-10): PMU 0x0402 0x09 -> 0x0b, AP GPIO 164 (BT_WAKE), UART3 baud registers (boot/uartpoke.c).
The only UART traffic is the 4-byte standard HCI Reset (01 03 0c 00), at true 3 Mbaud (+0x28 = 0x80000, the ADT transport-speed) and 115,200, with and without RTS/CTS.

  boot/bt_pinmux_ab.py

Needs /tmp/bt/{pinpoke (with `func`),i2ctransfer,uartpoke} on the iPad and boot/ipad_telnet_run.py. Stop btattach first. Do not run while another thread owns the iPad.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bt_3m_probe import TTY, probe, rd_pmu, sh  # noqa: E402

UART_PADS = (14, 15, 32, 33)  # TX, RX, RTS, CTS
FUNC_PINS = (14, 32)
RATES = [("3,000,000 (i=8 div 0)", 0x80000), ("115,200 (legacy div 12)", 0xC)]


def rd(pin):
    m = re.search(r"reg (0x[0-9a-f]+)", sh(f"cd /tmp/bt; ./pinpoke read {pin} 2>&1"))
    return int(m.group(1), 16) if m else None


def periph(v):
    return (v >> 5) & 3


def pads():
    return " ".join(f"{p}=0x{rd(p):08x}(f{periph(rd(p))})" for p in UART_PADS)


def main():
    for tool in ("pinpoke", "i2ctransfer", "uartpoke"):
        if "x" not in sh(f"ls -l /tmp/bt/{tool} 2>&1 | cut -c1-4"):
            sys.exit(f"/tmp/bt/{tool} is missing on the iPad")
    if "function must be 1 or 2" not in sh("cd /tmp/bt; ./pinpoke func 14 0 2>&1"):
        sys.exit("/tmp/bt/pinpoke has no `func` command; push the rebuilt pinpoke")
    if sh("ls /sys/class/bluetooth 2>&1 | head -1; ps | grep -c '[b]tattach'").splitlines()[-1] != "0":
        sys.exit("btattach is running; stop it first")
    orig = {p: rd(p) for p in FUNC_PINS}
    orig164 = rd(164)
    g2, usb = rd_pmu("0x04", "0x02"), rd_pmu("0x00", "0x10")
    orig_uart = sh("cd /tmp/bt; ./uartpoke get")
    mu = re.search(r"\+0x04=(0x\w+) \+0x08=(0x\w+) \+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig_uart)
    print(f"baseline pads: {pads()}; pin164 0x{orig164:08x}; 0x0402 {g2}; 0x0010 {usb}; uart: {orig_uart}")
    if None in orig.values() or orig164 is None or g2 != "0x09" or usb != "0x00" or not mu:
        sys.exit("unexpected baseline; nothing was written")
    if any(periph(v) != 2 for v in orig.values()):
        sys.exit("GPIO 14/32 are not on function 2 (has the DT changed?); nothing was written")
    o04, o08, o28, o34, o38 = mu.groups()
    ok = True
    try:
        for p in FUNC_PINS:
            print(sh(f"cd /tmp/bt; ./pinpoke func {p} 1"))
        ok = all(periph(rd(p)) == 1 for p in FUNC_PINS)
        print(f"pads after func 1: {pads()}")
        if ok:
            print(sh("cd /tmp/bt; ./pinpoke high 164"))
            ok = (rd(164) & 1) == 1
        if ok:
            sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b")
            g2n = rd_pmu("0x04", "0x02")
            print(f"0x0402 readback: {g2n}")
            ok = g2n == "0x0b"
        if ok:
            sh("sleep 1")
            if "x" in sh("ls -l /tmp/bt/uartpeek 2>&1 | cut -c1-4"):
                print("uart3 after power-up (UMSTAT +0x1c bit 0 = controller RTS):", sh("cd /tmp/bt; ./uartpeek 3 2>&1 | tr '\\n' ' '"))
            for label, r28 in RATES:
                for flow in (False, True):
                    print(f"{label:26s} {'rtscts' if flow else 'no-fc '}: {probe(r28, flow)}", flush=True)
        else:
            print("a write did not take; skipping the probe")
    finally:
        print("--- RESTORE")
        sh("killall btattach 2>/dev/null")
        sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09")
        sh(f"cd /tmp/bt; ./pinpoke restore 164 0x{orig164:08x}")
        sh(f"cd /tmp/bt; exec 3<>{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -cstopb -parenb 115200; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; ./uartpoke set {o28} {o34} {o38} >/dev/null; exec 3<&-")
        for p in FUNC_PINS:
            sh(f"cd /tmp/bt; ./pinpoke func {p} {periph(orig[p])}")
        g2f, usbf = rd_pmu("0x04", "0x02"), rd_pmu("0x00", "0x10")
        bad = [p for p in FUNC_PINS if rd(p) != orig[p]] + ([164] if rd(164) != orig164 else [])
        print(f"final pads: {pads()}; 0x0402 {g2f} (want 0x09); 0x0010 {usbf}; uart: {sh('cd /tmp/bt; ./uartpoke get')}")
        if g2f != "0x09" or bad:
            print(f"!!! RESTORE FAILED (pins {bad}): check the registers by hand")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
