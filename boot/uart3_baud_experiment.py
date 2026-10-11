#!/usr/bin/env python3
"""Measure what the Apple uart-version-1 register values actually do on the Bluetooth UART3 of the RUNNING iPad.

For each candidate (+0x08 UFCON, +0x28, +0x34, +0x38) the script writes the registers (boot/uartpoke.c, UART3 only), transmits a known number of zero bytes with the port held open
(so the tty layer does not reprogram the divider), waits until the UART's own transmitted-byte counter (/proc/tty/driver) has advanced by that many bytes (a true drain time, no
tty-buffer error), and prints the achieved baud rate (bytes*10/seconds). Round 1 (2026-10-11) showed the baud registers alone behave as legacy /16 plus fractional slots and cannot give 3 Mbaud;
round 2 showed the FIFO/control word (+0x08 = 0xc1 / 0x1c1) does not change the rate (all legacy /16 from 24 MHz). The agent's table is consistent with a 48 MHz input clock (2 x nclk), so round 3 showed UCON bits 8/10/11/15 change nothing; round 4 showed UCON bit 20 (iOS's uart-version-1 bit) raises the rate by ~sqrt(2) with zero slot words; round 5 showed slot words only slow it by 15/16; round 6 combines bit 20 with UCON bits 10/17 and UFCON 0x1c1.
The original register values are restored at the end in a finally block. The Bluetooth chip is not powered during this test; nothing else is touched.

  boot/uart3_baud_experiment.py

Expects /tmp/bt/uartpoke on the iPad (pushed over the USB link). Needs boot/ipad_telnet_run.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

TTY = "/dev/ttySAC1"
# (label, UCON or None, UFCON or None, +0x28, +0x34 or None, +0x38 or None, bytes); None = keep the original value.
# Round 4: UCON bit 20 (iOS's uart-version-1 bit) multiplies the rate by ~1.41 with zero slot words. Round 5: slot words only slow it by 15/16, as in legacy mode.
# iOS's target (24 MHz / (8 x (+0x28 + 1)): 0x19 -> 115.2 k) needs another ~1.41 on top. Round 6 combines bit 20 with the other bits iOS writes for version 1:
# UCON bit 10 (iOS baseline 0x405), UCON bit 17 (a helper at 0x2d76a58) and UFCON 0x1c1/0x131; reference with bit 20 alone at 28=0x19: ~81.5 k (nominal legacy 57.7 k, iOS target 115.2 k).
B20 = 0x100085
CANDIDATES = [
    ("control: nothing changed, 28=0x19 (legacy 57.7 k)", None, None, 0x19, None, None, 30_000),
    ("bit20 alone, 28=0x19 (round 4: ~81.5 k)", B20, None, 0x19, None, None, 30_000),
    ("bit20 + bit10 (0x100485), 28=0x19", 0x100485, None, 0x19, None, None, 30_000),
    ("bit20 + bit17 (0x120085), 28=0x19", 0x120085, None, 0x19, None, None, 30_000),
    ("bit20 + bit10 + bit17 (0x120485), 28=0x19", 0x120485, None, 0x19, None, None, 30_000),
    ("bit20 + UFCON 0x131, 28=0x19", B20, 0x131, 0x19, None, None, 30_000),
    ("bit20 + UFCON 0x1c1 (iOS v1), 28=0x19", B20, 0x1C1, 0x19, None, None, 30_000),
    ("all: 0x120485 + UFCON 0x1c1, 28=0x19", 0x120485, 0x1C1, 0x19, None, None, 30_000),
    ("all: 0x120485 + UFCON 0x1c1, 28=0 (iOS 3M without slots)", 0x120485, 0x1C1, 0x0, None, None, 600_000),
]


def sh(cmd, timeout=60):
    out, _ = run(cmd, timeout=timeout)
    return out.strip()


def main():
    if "x" not in sh("ls -l /tmp/bt/uartpoke 2>&1 | cut -c1-4"):
        sys.exit("/tmp/bt/uartpoke is missing on the iPad")
    if sh("ls /sys/class/bluetooth 2>&1 | head -1; ps | grep -c '[b]tattach'").splitlines()[-1] != "0":
        sys.exit("btattach is running; stop it first")
    orig = sh("cd /tmp/bt; ./uartpoke get")
    m = re.search(r"\+0x04=(0x\w+) \+0x08=(0x\w+) \+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig)
    if not m:
        sys.exit(f"cannot read the registers (is the new uartpoke on the iPad?): {orig}")
    o04, o08, o28, o34, o38 = m.groups()
    print(f"original: {orig}")
    try:
        for label, ucon, ufcon, r28, r34, r38, nbytes in CANDIDATES:
            pre = (f"./uartpoke ucon 0x{ucon:x} >/dev/null; " if ucon is not None else "") + (f"./uartpoke ufcon 0x{ufcon:x} >/dev/null; " if ufcon is not None else "")
            cmd = (
                f"cd /tmp/bt; exec 3<{TTY}; stty -F {TTY} raw -echo -crtscts clocal 115200; "
                "tx() { grep '^1:' /proc/tty/driver/s3c2410_serial | sed 's/.*tx:\\([0-9]*\\).*/\\1/'; }; "
                f"{pre}./uartpoke set 0x{r28:x} {('0x%x' % r34) if r34 is not None else o34} {('0x%x' % r38) if r38 is not None else o38} >/dev/null; "
                "c0=$(tx); t0=$(cut -d' ' -f1 /proc/uptime); "
                f"dd if=/dev/zero of={TTY} bs=1000 count={nbytes // 1000} 2>/dev/null; "
                f"s0=${{t0%.*}}; while [ $(( $(tx) - c0 )) -lt {nbytes} ]; do "
                "u=$(cut -d' ' -f1 /proc/uptime); if [ ${u%.*} -gt $((s0 + 30)) ]; then echo STALLED; break; fi; done; "
                "t1=$(cut -d' ' -f1 /proc/uptime); "
                "echo \"$t0 $t1\"; ./uartpoke get; exec 3<&-"
            )
            out = sh(cmd, timeout=180)
            if "STALLED" in out:
                print(f"{label}: TRANSMIT STALLED (the transmitter did not finish within 30 s)", flush=True)
                continue
            nums = re.findall(r"^([\d.]+) ([\d.]+)$", out, re.M)
            if not nums:
                print(f"{label}: no timing ({out!r})")
                continue
            dt = float(nums[0][1]) - float(nums[0][0])
            baud = nbytes * 10 / dt if dt > 0 else 0
            print(f"{label}: {nbytes} bytes drained in {dt:.2f} s -> ~{baud:,.0f} baud", flush=True)
    finally:
        print("--- RESTORE")
        print(sh(f"cd /tmp/bt; exec 3<{TTY}; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; ./uartpoke set {o28} {o34} {o38}; exec 3<&-"))
        print(sh("cd /tmp/bt; ./uartpoke get"))


if __name__ == "__main__":
    main()
