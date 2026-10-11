#!/usr/bin/env python3
"""Listen on the Bluetooth UART3 of the RUNNING iPad WHILE the controller is powered up: does it announce itself (a first byte or event) without being asked?

Every earlier probe sent an HCI Reset after power was applied and listened afterwards. Here, for each rate, the port is opened first with a reader running, and only then are BT_WAKE (AP GPIO 164) and power-enable (PMU 0x0402 0x09 -> 0x0b) asserted; the reader runs for a few
seconds; then both are restored (a power cycle between rates). Nothing is transmitted on the UART. Approved writes as in boot/bt_wake_experiment.py (user, 2026-10-10), plus the UART3-only baud registers (boot/uartpoke.c); everything restored in a finally block.

  boot/bt_powerup_listen.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

TTY = "/dev/ttySAC1"
RATES = [("115,200", 0xC), ("3,000,000", 0x80000), ("1,500,000", 0x0), ("921,600-ish", 0x30001)]


def sh(cmd, timeout=60):
    out, _ = run(cmd, timeout=timeout)
    return out.strip()


def rd_pmu(hi, lo):
    return sh(f"cd /tmp/bt; ./i2ctransfer -f -y 0 w2@0x3c {hi} {lo} r1@0x3c 2>&1").splitlines()[-1].strip()


def rd_pin():
    m = re.search(r"reg (0x[0-9a-f]+)", sh("cd /tmp/bt; ./pinpoke read 164 2>&1"))
    return m.group(1) if m else None


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
    try:
        for label, r28 in RATES:
            cmd = (
                f"cd /tmp/bt; exec 3<>{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -parenb -cstopb 115200; ./uartpoke set 0x{r28:x} 0x0 0x0 >/dev/null; "
                ": > /tmp/bt/rx.bin; cat <&3 > /tmp/bt/rx.bin & p=$!; sleep 0.5; "
                "./pinpoke high 164 >/dev/null; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b; sleep 4; "
                "echo \"during power-up: rx_bytes=$(wc -c < /tmp/bt/rx.bin) $(od -An -tx1 /tmp/bt/rx.bin | head -2 | tr -s ' ' | tr '\\n' ' ')\"; "
                f"./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09; ./pinpoke restore 164 {orig_pin} >/dev/null; sleep 1; "
                "echo \"after power-down: rx_bytes=$(wc -c < /tmp/bt/rx.bin)\"; kill $p 2>/dev/null; exec 3<&-"
            )
            out = sh(cmd, timeout=40)
            print(f"{label:12s}: " + " | ".join(out.splitlines()[-2:]), flush=True)
    finally:
        print("--- RESTORE")
        sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09")
        sh(f"cd /tmp/bt; ./pinpoke restore 164 {orig_pin}")
        sh(f"cd /tmp/bt; exec 3<>{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -cstopb -parenb 115200; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; ./uartpoke set {o28} {o34} {o38} >/dev/null; exec 3<&-")
        g2f, pinf, usbf = rd_pmu("0x04", "0x02"), rd_pin(), rd_pmu("0x00", "0x10")
        print(f"final: 0x0402 {g2f} (want 0x09), pin164 {pinf} (want {orig_pin}), 0x0010 {usbf}")
        print("battery:", sh("tablet-status | sed -n 2,3p | tr '\\n' ' '"))
        if g2f != "0x09" or pinf != orig_pin:
            print("!!! RESTORE FAILED: check the registers by hand")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
