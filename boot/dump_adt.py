#!/usr/bin/env python3
"""Capture PongoOS's textual Apple Device Tree dump without printing it."""

import argparse
import hashlib
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import usb.core
except ModuleNotFoundError as error:
    raise SystemExit(
        "PyUSB is required; run this through `nix develop -c python3`"
    ) from error


VID, PID = 0x05AC, 0x4141
MAX_BYTES = 8 * 1024 * 1024
REPO = Path(__file__).resolve().parent.parent


def read_stdout(device):
    return bytes(device.ctrl_transfer(0xA1, 1, 0, 0, 512, timeout=1000)).rstrip(b"\0")


def wait_for_pongo(seconds):
    deadline = time.monotonic() + seconds
    while True:
        device = usb.core.find(idVendor=VID, idProduct=PID)
        if device is not None:
            return device
        if time.monotonic() >= deadline:
            raise RuntimeError("PongoOS USB device 05ac:4141 was not found")
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def drain_stdout(device):
    """Discard stale Pongo output, stopping after 250 ms of silence."""
    started = time.monotonic()
    quiet_since = None
    while quiet_since is None or time.monotonic() - quiet_since < 0.25:
        if time.monotonic() - started >= 5:
            raise RuntimeError("PongoOS stdout did not become idle before capture")
        if read_stdout(device):
            quiet_since = None
        elif quiet_since is None:
            quiet_since = time.monotonic()
        time.sleep(0.01)


def capture_adt(device, timeout, idle):
    device.ctrl_transfer(0x21, 3, 0, 0, b"dt\n", timeout=5000)
    started = time.monotonic()
    last_data = None
    captured = bytearray()

    while time.monotonic() - started < timeout:
        chunk = read_stdout(device)
        now = time.monotonic()
        if chunk:
            captured.extend(chunk)
            last_data = now
            if len(captured) > MAX_BYTES:
                raise RuntimeError(f"ADT output exceeded the {MAX_BYTES}-byte safety limit")
        elif last_data is not None and now - last_data >= idle:
            return bytes(captured)
        else:
            time.sleep(0.01)

    raise RuntimeError(f"ADT output did not become idle within {timeout:g} seconds")


def validate_j81(data, minimum):
    text = data.decode("utf-8", "replace")
    checks = {
        f"at least {minimum} bytes": len(data) >= minimum,
        "target-type J81": re.search(r"(?m)^target-type\s+J81\s*$", text) is not None,
        "platform-name t7001": "platform-name" in text and "t7001" in text,
        "regulatory model A1566": "regulatory-model-number" in text and "A1566" in text,
        "device-tree root": re.search(r"(?m)^name\s+device-tree\s*$", text) is not None,
    }
    return [name for name, passed in checks.items() if not passed]


def safe_output(path, parser):
    path = path.expanduser().resolve()
    try:
        relative = path.relative_to(REPO)
    except ValueError:
        relative = None
    if relative is not None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(relative)], cwd=REPO, check=False
        )
        if ignored.returncode != 0:
            parser.error("an ADT capture inside the repository must be Git-ignored")
    if path.exists() or path.with_name(path.name + ".partial").exists():
        parser.error(f"refusing to overwrite {path} or its .partial file")
    return path


def write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(
        description="Safely capture a connected J81 ADT from PongoOS"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=REPO / "artifacts/adt" / f"{stamp}-j81.adt",
    )
    parser.add_argument("--wait-seconds", type=float, default=60)
    parser.add_argument("--timeout", type=float, default=90, help="whole-capture timeout")
    parser.add_argument(
        "--idle-seconds", type=float, default=2, help="silence that marks end of output"
    )
    parser.add_argument("--min-bytes", type=int, default=200_000)
    args = parser.parse_args()
    if args.wait_seconds < 0 or min(args.timeout, args.idle_seconds, args.min_bytes) <= 0:
        parser.error("wait must be non-negative; capture limits must be positive")
    output = safe_output(args.output, parser)

    try:
        device = wait_for_pongo(args.wait_seconds)
        device.set_configuration()
        drain_stdout(device)
        data = capture_adt(device, args.timeout, args.idle_seconds)
    except (usb.core.USBError, RuntimeError) as error:
        raise SystemExit(f"ADT capture failed: {error}") from error

    failures = validate_j81(data, args.min_bytes)
    if failures:
        partial = output.with_name(output.name + ".partial")
        write_private(partial, data)
        raise SystemExit(
            f"ADT validation failed ({'; '.join(failures)}); partial capture saved to {partial}"
        )

    write_private(output, data)
    digest = hashlib.sha256(data).hexdigest()
    print(f"Captured J81 ADT: {output}")
    print(f"bytes={len(data)} sha256={digest}")
    print("Contains device identifiers and calibration: keep private and never commit it.")


if __name__ == "__main__":
    main()
