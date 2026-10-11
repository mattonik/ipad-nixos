#!/usr/bin/env python3
"""Measure what the Apple uart-version-1 baud register values actually do on the Bluetooth UART3 of the RUNNING iPad.

For each candidate (+0x28, +0x34, +0x38) from research/2026-10-11-uart-baud-register-semantics.md the script writes the three registers (boot/uartpoke.c, UART3 only), transmits a
known number of zero bytes with the port held open (so the tty layer does not reprogram the divider), times the drained transmit with /proc/uptime, and prints the
achieved baud rate (bytes*10/seconds). The original register values are restored at the end in a finally block. The Bluetooth chip is not powered during this test; nothing else is touched.

  boot/uart3_baud_experiment.py

Expects /tmp/bt/uartpoke on the iPad (pushed over the USB link). Needs boot/ipad_telnet_run.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

TTY = "/dev/ttySAC1"
# (label, +0x28, +0x34, +0x38, expected baud under the research-note model, bytes to send)
CANDIDATES = [
    ("legacy 0/0/0 (control, expect ~1.5M)", 0x0, 0x0, 0x0, 1_500_000, 300_000),
    ("table 3M: 0x0/0x55555555/0x55555555", 0x0, 0x55555555, 0x55555555, 3_000_000, 600_000),
    ("table 115200: 0x19/0x55555555 both", 0x19, 0x55555555, 0x55555555, 115_200, 30_000),
    ("legacy 0x19/0/0 (control, expect ~57.6k)", 0x19, 0x0, 0x0, 57_600, 15_000),
    ("table 1.5M: 0x1/0x55555555 both", 0x1, 0x55555555, 0x55555555, 1_500_000, 300_000),
    ("table 921600: 0x2/0/0", 0x2, 0x0, 0x0, 921_600, 200_000),
    ("0/0x55555555/0 (only 0x34)", 0x0, 0x55555555, 0x0, 0, 300_000),
    ("0/0/0x55555555 (only 0x38)", 0x0, 0x0, 0x55555555, 0, 300_000),
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
    m = re.search(r"\+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig)
    if not m:
        sys.exit(f"cannot read the registers: {orig}")
    o28, o34, o38 = m.groups()
    print(f"original: {orig}")
    try:
        for label, r28, r34, r38, expect, nbytes in CANDIDATES:
            cmd = (
                f"cd /tmp/bt; exec 3<{TTY}; stty -F {TTY} raw -echo -crtscts clocal 115200; "
                f"./uartpoke set 0x{r28:x} 0x{r34:x} 0x{r38:x} >/dev/null; "
                "t0=$(cut -d' ' -f1 /proc/uptime); "
                f"dd if=/dev/zero of={TTY} bs=1000 count={nbytes // 1000} 2>/dev/null; "
                "t1=$(cut -d' ' -f1 /proc/uptime); "
                "echo \"$t0 $t1\"; ./uartpoke get; exec 3<&-"
            )
            out = sh(cmd, timeout=120)
            nums = re.findall(r"^([\d.]+) ([\d.]+)$", out, re.M)
            if not nums:
                print(f"{label}: no timing ({out!r})")
                continue
            dt = float(nums[0][1]) - float(nums[0][0])
            baud = nbytes * 10 / dt if dt > 0 else 0
            note = f" (model expects {expect})" if expect else ""
            print(f"{label}: {nbytes} bytes in {dt:.2f} s -> ~{baud:,.0f} baud{note}", flush=True)
    finally:
        print("--- RESTORE")
        print(sh(f"cd /tmp/bt; exec 3<{TTY}; ./uartpoke set {o28} {o34} {o38}; exec 3<&-"))
        print(sh("cd /tmp/bt; ./uartpoke get"))


if __name__ == "__main__":
    main()
