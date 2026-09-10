#!/usr/bin/env python3
"""Collect a bounded, read-only J81 Bluetooth/UART3 snapshot over telnet.

This deliberately has no arbitrary remote-command option and no PMIC write
primitive.  The i2ctransfer commands below use the PMIC register address as a
read transaction's address phase (w2 ... rN); they do not write register data.
Run from the repository root:

    python3 boot/bt_probe.py --repeat 3 --interval 2

Use --output only for a private ignored capture under artifacts/live/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
import time

from ipad_console import IPadShell


COMMANDS = (
    (
        "identity",
        "uname -a; cat /proc/device-tree/model 2>/dev/null; "
        "tr '\\0' '\\n' </proc/device-tree/compatible 2>/dev/null",
    ),
    (
        "uart3",
        "ls -la /dev/ttySAC* 2>&1; "
        "cat /proc/tty/driver/s3c2410_serial 2>&1 || true; "
        "find /sys/bus/serial/devices -maxdepth 2 -type l -print 2>&1",
    ),
    (
        "bluetooth",
        "ls -la /sys/class/bluetooth 2>&1; "
        "for h in /sys/class/bluetooth/hci*; do "
        "[ -d \"$h\" ] || continue; echo \"[$h]\"; "
        "for f in address name type modalias; do "
        "[ -r \"$h/$f\" ] && { printf '%s: ' \"$f\"; cat \"$h/$f\"; }; "
        "done; done; "
        "ps 2>&1 | grep -E '[b]tattach|[h]ci' || true; "
        "cat /tmp/btattach.log 2>&1 || true",
    ),
    (
        "pmic-gpio2",
        "i2ctransfer -f -y 0 w2@0x3c 0x03 0xe6 r2; "
        "i2ctransfer -f -y 0 w2@0x3c 0x00 0x63 r1",
    ),
    (
        "pmic-status",
        "i2ctransfer -f -y 0 w2@0x3c 0x00 0x10 r1; "
        "i2ctransfer -f -y 0 w2@0x3c 0x00 0x50 r14; "
        "i2ctransfer -f -y 0 w2@0x3c 0x00 0x60 r13",
    ),
    (
        "gpio-and-pinctrl",
        "cat /sys/kernel/debug/gpio 2>&1 | head -n 160; "
        "for f in /sys/kernel/debug/pinctrl/*/pinmux-pins "
        "/sys/kernel/debug/pinctrl/*/pins; do "
        "[ -r \"$f\" ] && { echo \"--- $f\"; "
        "grep -Ei 'gpio|uart|14|32|164' \"$f\" | head -n 120; }; done",
    ),
    (
        "power-and-interrupts",
        "cat /sys/kernel/debug/pm_genpd/pm_genpd_summary 2>&1; "
        "grep -Ei '20a0cc000|ttySAC1|bluetooth|hci|uart' /proc/interrupts "
        "2>&1 || true",
    ),
    (
        "kernel-log",
        "dmesg | grep -iE '20a0cc000|ttySAC1|bluetooth|hci|bcm43|uart|gpio' "
        "| tail -n 100",
    ),
)


_MAC = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_BDADDR = re.compile(r"(?i)(local-bd-address|bdaddr|mac(?:address)?)\s*[:=]\s*\S+")


def redact(text: str) -> str:
    """Remove addresses that are not needed for the UART/PMIC diagnosis."""
    text = _BDADDR.sub(lambda match: match.group(1) + "=<redacted>", text)
    return _MAC.sub("<redacted-mac>", text)


def collect_snapshot(shell: IPadShell, timeout: float = 10.0) -> str:
    """Run the fixed read-only command set once and return a redacted report."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sections = [f"J81 Bluetooth read-only snapshot: {stamp}"]
    for name, command in COMMANDS:
        try:
            output = shell.run(command, timeout=timeout)
        except Exception as exc:  # keep later probes useful if one path is absent
            output = f"probe error: {type(exc).__name__}: {exc}"
        sections.append(f"\n===== {name} =====\n{redact(output).rstrip()}")
    return "\n".join(sections) + "\n"


def _output_path(raw: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    allowed = (root / "artifacts" / "live").resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if allowed not in path.parents:
        raise ValueError("--output must be under artifacts/live/")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, choices=range(1, 31))
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", help="private capture path under artifacts/live/")
    args = parser.parse_args()
    if args.interval < 0 or args.timeout <= 0:
        parser.error("--interval must be non-negative and --timeout must be positive")

    shell = IPadShell()
    reports: list[str] = []
    try:
        shell.connect()
        for index in range(args.repeat):
            reports.append(collect_snapshot(shell, timeout=args.timeout))
            if index + 1 < args.repeat:
                time.sleep(args.interval)
    except OSError as exc:
        print(f"telnet connection failed: {exc}", file=sys.stderr)
        return 2
    finally:
        shell.close()

    report = "\n".join(reports)
    if args.output:
        path = _output_path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(report)
        print(f"saved private read-only capture: {path}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
