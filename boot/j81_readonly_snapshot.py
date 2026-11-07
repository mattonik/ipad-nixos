#!/usr/bin/env python3
"""Capture one small, read-only J81 Linux inventory over the existing telnet shell."""
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Keep device output to mapping, boot identity, and display/controller context.
COMMANDS = [
    ("kernel", "uname -a; cat /proc/version"),
    ("boot_identity", "cat /proc/sys/kernel/random/boot_id; sha256sum /sys/kernel/notes"),
    ("iomem", "cat /proc/iomem"),
    ("memory", "cat /proc/meminfo"),
    ("fdt_identity", "for f in model compatible; do p=/sys/firmware/devicetree/base/$f; if [ -r \"$p\" ]; then printf '%s: ' \"$f\"; tr '\\000' '\\n' < \"$p\"; fi; done"),
    ("fdt_memory_ranges", "for p in /sys/firmware/devicetree/base/memory* /sys/firmware/devicetree/base/reserved-memory/* /sys/firmware/devicetree/base/chosen; do [ -d \"$p\" ] || continue; for a in reg available linux,usable-memory-range; do [ -r \"$p/$a\" ] && { echo \"[$p/$a hex bytes]\"; od -An -v -tx1 \"$p/$a\"; }; done; done"),
    ("fdt_display_controller", "find /sys/firmware/devicetree/base -type d 2>/dev/null | grep -iE 'display|dcp|pmgr|gpu|framebuffer|controller' | while IFS= read -r p; do echo \"[$p]\"; for a in compatible reg status clock-names power-domains; do [ -r \"$p/$a\" ] && { printf '%s: ' \"$a\"; tr '\\000' ' ' < \"$p/$a\"; echo; }; done; done"),
    ("sysfs_display_controller", "for p in /sys/bus/platform/devices/*; do case \"$p\" in *display*|*dcp*|*pmgr*|*gpu*|*framebuffer*|*controller*) echo \"[$p]\"; for a in uevent resource; do [ -r \"$p/$a\" ] && { echo \"--$a\"; cat \"$p/$a\"; }; done; for a in runtime_status runtime_usage; do [ -r \"$p/power/$a\" ] && { printf '%s: ' \"$a\"; cat \"$p/power/$a\"; }; done;; esac; done"),
    ("display_classes", "for p in /sys/class/graphics/* /sys/class/drm/* /sys/class/backlight/*; do [ -e \"$p\" ] || continue; echo \"[$p]\"; for a in name modes status enabled actual_brightness brightness max_brightness; do [ -r \"$p/$a\" ] && { printf '%s: ' \"$a\"; cat \"$p/$a\"; }; done; done"),
    ("relevant_dmesg", "dmesg | grep -iE 'pmgr|display|dcp|framebuffer|drm|gpu|iomem|memory:|reserved memory' | tail -n 250"),
]
_MAC = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
_UUID = re.compile(r"(?i)\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b")


def sanitize(text):
    return _UUID.sub("[UUID]", _MAC.sub("[MAC]", text))


def capture(shell, parent, now=None):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    out = parent / ("j81-readonly-" + (now or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    out.mkdir(mode=0o700)
    for name, command in COMMANDS:
        result = sanitize(shell.run(command, timeout=30, check=False))
        fd = os.open(out / f"{name}.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(result + "\n")
    return out


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_parent", nargs="?", default="artifacts/live")
    args = parser.parse_args()
    from ipad_console import IPadShell
    shell = IPadShell()
    try:
        shell.connect()
        out = capture(shell, args.output_parent)
    finally:
        shell.close()
    print(f"read-only snapshot saved privately: {out}")


if __name__ == "__main__":
    main()
