#!/usr/bin/env python3
"""Measure what the Apple uart-version-1 register values actually do on the Bluetooth UART3 of the RUNNING iPad.

For each candidate (+0x08 UFCON, +0x28, +0x34, +0x38) the script writes the registers (boot/uartpoke.c, UART3 only), transmits a known number of zero bytes with the port held open
(so the tty layer does not reprogram the divider), waits until the UART's own transmitted-byte counter (/proc/tty/driver) has advanced by that many bytes (a true drain time, no
tty-buffer error), and prints the achieved baud rate (bytes*10/seconds). Round 1 (2026-10-11) showed the baud registers alone behave as legacy /16 plus fractional slots and cannot give 3 Mbaud;
round 2 showed the FIFO/control word (+0x08 = 0xc1 / 0x1c1) does not change the rate (all legacy /16 from 24 MHz). The agent's table is consistent with a 48 MHz input clock (2 x nclk), so round 3 showed UCON bits 8/10/11/15 change nothing; round 4 showed UCON bit 20 (iOS's uart-version-1 bit) raises the rate by ~sqrt(2) with zero slot words; round 5 showed slot words only slow it by 15/16; round 6 combined bit 20 with UCON bits 10/17 and UFCON (no further gain); round 7 scans each remaining UCON bit on top of bit 20.
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
# Round 8 (2026-10-11): the UPPER HALF of +0x28 is a sampling-factor field: with UCON untouched, 8N1, baud = 24 MHz / ((16 - i) x (div + 1)) for i = 0..4 (measured x16/(16-i) exactly).
# Round 9: extend i upward; i = 8 with div 0 should be 3.0 M (24 MHz / 8). At div 0x19 each i gives 57.7 k x 16/(16-i); the div-0x19 rows are CPU-safe line-rate checks.
CANDIDATES = [("control: 28=0x19 (legacy 57.7 k)", None, None, 0x19, None, None, 20_000)]
for _i in (5, 6, 7, 8, 9, 10, 11, 12):
    CANDIDATES.append((f"28=0x{(_i << 16) | 0x19:x} (i={_i}, factor {16 - _i}, div 25: expect {24e6 / ((16 - _i) * 26):,.0f})", None, None, (_i << 16) | 0x19, None, None, 20_000))
for _i in (8, 10, 12):
    CANDIDATES.append((f"28=0x{(_i << 16) | 0x03:x} (i={_i}, factor {16 - _i}, div 3: expect {24e6 / ((16 - _i) * 4):,.0f})", None, None, (_i << 16) | 0x03, None, None, 300_000))
    CANDIDATES.append((f"28=0x{(_i << 16) | 0x00:x} (i={_i}, factor {16 - _i}, div 0: expect {24e6 / (16 - _i):,.0f})", None, None, (_i << 16) | 0x00, None, None, 600_000))


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
