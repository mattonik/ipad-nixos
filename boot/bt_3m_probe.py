#!/usr/bin/env python3
"""Probe the Bluetooth controller at TRUE high baud rates on the RUNNING iPad: power-enable + BT_WAKE asserted, UART3 set to a real 3 Mbaud, raw HCI Reset.

Discovery (2026-10-11, research/2026-10-11-uart3-register-capture.md rounds 8-9): the upper half of the Apple UART's +0x28 is a sampling-factor field, baud = 24 MHz / ((16 - i) x (div + 1)) with
factor 16 - i = 4..16; so 3,000,000 baud = i 8, div 0 = +0x28 = 0x80000. Until now no probe ever ran at a rate iOS actually uses on a cold controller (3 Mbaud from the first byte).

Approved writes (the user, 2026-10-10, each with readback and revert): PMU 0x0402 (0x09 -> 0x0b) and AP GPIO 164 (BT_WAKE, via boot/pinpoke.c); plus the UART3-only baud registers (boot/uartpoke.c). Everything is restored in a
finally block. The only UART traffic is the 4-byte standard HCI Reset (01 03 0c 00).

  boot/bt_3m_probe.py [--frames]     (--frames: 8N1, 8E1, 8O1, 8N2 at 3 M, 1.5 M and 115.2 k)

Needs /tmp/bt/{pinpoke,i2ctransfer,uartpoke} on the iPad (pushed over the USB link) and boot/ipad_telnet_run.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

TTY = "/dev/ttySAC1"
# (label, +0x28 value written after stty at 115200)
RATES = [
    ("3,000,000 (i=8 div 0)", 0x80000),
    ("2,000,000 (i=4 div 0)", 0x40000),
    ("4,000,000 (i=10 div 0)", 0xA0000),
    ("1,500,000 (legacy div 0)", 0x0),
    ("921,600-ish 923k (i=3 div 1)", 0x30001),
    ("115,200 (legacy div 12)", 0xC),
    ("750,000 (legacy div 1)", 0x1),
]
# Frame formats (stty flags): the ADT says transport-encoding = 3, meaning not yet known; round 1 of this script used 8N1 only.
FRAMES = [("8N1", "cs8 -parenb -cstopb"), ("8E1", "cs8 parenb -parodd -cstopb"), ("8O1", "cs8 parenb parodd -cstopb"), ("8N2", "cs8 -parenb cstopb")]
if "--frames" not in sys.argv:
    FRAMES = FRAMES[:1]
else:
    RATES = [r for r in RATES if r[0].startswith(("3,000,000", "115,200", "1,500,000"))]


def sh(cmd, timeout=60):
    out, _ = run(cmd, timeout=timeout)
    return out.strip()


def rd_pmu(hi, lo):
    return sh(f"cd /tmp/bt; ./i2ctransfer -f -y 0 w2@0x3c {hi} {lo} r1@0x3c 2>&1").splitlines()[-1].strip()


def rd_pin():
    m = re.search(r"reg (0x[0-9a-f]+)", sh("cd /tmp/bt; ./pinpoke read 164 2>&1"))
    return m.group(1) if m else None


def probe(r28, flow, frame="cs8 -parenb -cstopb"):
    fc = "crtscts" if flow else "-crtscts"
    cmd = (
        f"cd /tmp/bt; exec 3<>{TTY}; stty -F {TTY} raw -echo {fc} clocal {frame} 115200; ./uartpoke set 0x{r28:x} 0x0 0x0 >/dev/null; "
        ": > /tmp/bt/rx.bin; cat <&3 > /tmp/bt/rx.bin & p=$!; sleep 0.3; printf '\\001\\003\\014\\000' >&3; sleep 2; kill $p 2>/dev/null; "
        "echo \"rx_bytes=$(wc -c < /tmp/bt/rx.bin) $(od -An -tx1 /tmp/bt/rx.bin | head -2 | tr -s ' ' | tr '\\n' ' ')\"; exec 3<&-"
    )
    out = sh(cmd, timeout=40)
    return out.splitlines()[-1] if out else "no output"


def main():
    for tool in ("pinpoke", "i2ctransfer", "uartpoke"):
        if "x" not in sh(f"ls -l /tmp/bt/{tool} 2>&1 | cut -c1-4"):
            sys.exit(f"/tmp/bt/{tool} is missing on the iPad")
    if sh("ls /sys/class/bluetooth 2>&1 | head -1; ps | grep -c '[b]tattach'").splitlines()[-1] != "0":
        sys.exit("btattach is running; stop it first")
    orig_pin, g2, usb = rd_pin(), rd_pmu("0x04", "0x02"), rd_pmu("0x00", "0x10")
    orig_uart = sh("cd /tmp/bt; ./uartpoke get")
    mu = re.search(r"\+0x04=(0x\w+) \+0x08=(0x\w+) \+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig_uart)
    print(f"baseline: pin164 {orig_pin}, 0x0402 {g2}, 0x0010 {usb}; uart: {orig_uart}")
    if not orig_pin or g2 != "0x09" or usb != "0x00" or not mu:
        sys.exit("unexpected baseline; nothing was written")
    o04, o08, o28, o34, o38 = mu.groups()
    ok = True
    try:
        print(sh("cd /tmp/bt; ./pinpoke high 164"))
        if (int(rd_pin(), 16) & 1) != 1:
            print("BT_WAKE did not go high; stopping")
            ok = False
        if ok:
            sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b")
            g2n = rd_pmu("0x04", "0x02")
            print(f"0x0402 readback: {g2n}")
            ok = g2n == "0x0b"
        if ok:
            sh("sleep 1")
            for fname, fflags in FRAMES:
                for label, r28 in RATES:
                    for flow in (False, True):
                        print(f"{fname} {label:32s} {'rtscts' if flow else 'no-fc '}: {probe(r28, flow, fflags)}", flush=True)
    finally:
        print("--- RESTORE")
        sh("killall btattach 2>/dev/null")
        sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09")
        sh(f"cd /tmp/bt; ./pinpoke restore 164 {orig_pin}")
        sh(f"cd /tmp/bt; exec 3<>{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -cstopb -parenb 115200; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; ./uartpoke set {o28} {o34} {o38} >/dev/null; exec 3<&-")
        g2f, pinf, usbf = rd_pmu("0x04", "0x02"), rd_pin(), rd_pmu("0x00", "0x10")
        print(f"final: 0x0402 {g2f} (want 0x09), pin164 {pinf} (want {orig_pin}), 0x0010 {usbf}, uart: {sh('cd /tmp/bt; ./uartpoke get')}")
        print("battery:", sh("tablet-status | sed -n 2,3p | tr '\\n' ' '"))
        if g2f != "0x09" or pinf != orig_pin:
            print("!!! RESTORE FAILED: check the registers by hand")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
