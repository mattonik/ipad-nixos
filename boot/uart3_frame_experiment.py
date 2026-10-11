#!/usr/bin/env python3
"""Separate the TRUE line baud rate from per-byte overhead on the Bluetooth UART3 of the RUNNING iPad.

Byte throughput alone cannot tell "line rate x 10/7 with 10-bit frames" from "line rate x 2 with ~14-bit effective frames" (rounds 4-7 of the Apple baud-register study, research/2026-10-11-uart3-register-capture.md).
If one byte takes (n + g) bit-times for an n-bit frame (start + data + parity + stop) and g is a fixed per-byte overhead, then time per byte = (n + g) / baud: a straight line in n whose SLOPE is 1/baud. This script
transmits N zero bytes (true-drain timing via the UART's transmitted-byte counter) with frame formats 5N1, 6N1, 7N1, 8N1, 8N2, 8E2 (n = 7, 8, 9, 10, 11, 12) in a few register modes, and prints the time per byte and the least-squares
slope and intercept, i.e. the line baud and the overhead.

The tty layer programs ULCON for each frame (via stty); this script then writes UCON/+0x28/+0x34/+0x38 (boot/uartpoke.c, UART3 only) and restores the originals at the end (finally block). The chip is not powered; nothing else is touched.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

TTY = "/dev/ttySAC1"
FRAMES = [("cs5 -cstopb -parenb", 7), ("cs6 -cstopb -parenb", 8), ("cs7 -cstopb -parenb", 9), ("cs8 -cstopb -parenb", 10), ("cs8 cstopb -parenb", 11), ("cs8 cstopb parenb -parodd", 12)]
# (label, UCON or None, +0x28, +0x34, +0x38, bytes per frame test)
MODES = [
    ("legacy 28=0x19 (expect baud 57.7 k, gap 0)", None, 0x19, 0x0, 0x0, 20_000),
    ("bit20 28=0x19", 0x100085, 0x19, 0x0, 0x0, 20_000),
    ("bit20 28=0x01", 0x100085, 0x01, 0x0, 0x0, 200_000),
    ("bit20 28=0x00", 0x100085, 0x00, 0x0, 0x0, 300_000),
]


def sh(cmd, timeout=240):
    out, _ = run(cmd, timeout=timeout)
    return out.strip()


def measure(flags, ucon, r28, r34, r38, nbytes):
    pre = f"./uartpoke ucon 0x{ucon:x} >/dev/null; " if ucon is not None else ""
    cmd = (
        f"cd /tmp/bt; exec 3<{TTY}; stty -F {TTY} raw -echo -crtscts clocal {flags} 115200; "
        "tx() { grep '^1:' /proc/tty/driver/s3c2410_serial | sed 's/.*tx:\\([0-9]*\\).*/\\1/'; }; "
        f"{pre}./uartpoke set 0x{r28:x} 0x{r34:x} 0x{r38:x} >/dev/null; "
        "c0=$(tx); t0=$(cut -d' ' -f1 /proc/uptime); "
        f"dd if=/dev/zero of={TTY} bs=1000 count={nbytes // 1000} 2>/dev/null; "
        f"s0=${{t0%.*}}; while [ $(( $(tx) - c0 )) -lt {nbytes} ]; do "
        "u=$(cut -d' ' -f1 /proc/uptime); if [ ${u%.*} -gt $((s0 + 40)) ]; then echo STALLED; break; fi; done; "
        "t1=$(cut -d' ' -f1 /proc/uptime); echo \"$t0 $t1\"; exec 3<&-"
    )
    out = sh(cmd)
    if "STALLED" in out:
        return None
    m = re.findall(r"^([\d.]+) ([\d.]+)$", out, re.M)
    return (float(m[0][1]) - float(m[0][0])) if m else None


def fit(points):
    n = len(points)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    return slope, (sy - slope * sx) / n


def main():
    if "x" not in sh("ls -l /tmp/bt/uartpoke 2>&1 | cut -c1-4"):
        sys.exit("/tmp/bt/uartpoke is missing on the iPad")
    if sh("ls /sys/class/bluetooth 2>&1 | head -1; ps | grep -c '[b]tattach'").splitlines()[-1] != "0":
        sys.exit("btattach is running; stop it first")
    orig = sh("cd /tmp/bt; ./uartpoke get")
    m = re.search(r"\+0x04=(0x\w+) \+0x08=(0x\w+) \+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig)
    if not m:
        sys.exit(f"cannot read the registers: {orig}")
    o04, o08, o28, o34, o38 = m.groups()
    print(f"original: {orig}")
    try:
        for label, ucon, r28, r34, r38, nbytes in MODES:
            pts = []
            print(f"== {label}")
            for flags, nbits in FRAMES:
                dt = measure(flags, ucon, r28, r34, r38, nbytes)
                if dt is None:
                    print(f"   n={nbits:2d} ({flags}): stalled / no timing")
                    continue
                tb = dt / nbytes
                pts.append((nbits, tb))
                print(f"   n={nbits:2d} ({flags:26s}): {nbytes} bytes in {dt:5.2f} s -> {tb * 1e6:9.2f} us/byte", flush=True)
            if len(pts) >= 3:
                slope, icpt = fit(pts)
                print(f"   fit: bit time {slope * 1e6:.3f} us -> LINE BAUD ~{1 / slope:,.0f}; overhead {icpt / slope:+.2f} bit-times per byte", flush=True)
    finally:
        print("--- RESTORE")
        print(sh(f"cd /tmp/bt; exec 3<{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -cstopb -parenb 115200; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; ./uartpoke set {o28} {o34} {o38}; exec 3<&-"))


if __name__ == "__main__":
    main()
