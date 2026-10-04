#!/usr/bin/env python3
"""Run explicit host-only checks; report unavailable source/build checks as skips.

No downloads, Nix builds, USB access or device connections are performed.
Run from any directory. Tests run in isolated Python processes at repo root.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
# Explicit list: newly added test scripts are reviewed before auto-execution.
HOST_TESTS = (
    "boot/test_bt_probe.py",
    "boot/test_dump_adt.py",
    "boot/test_inspect_j81_touch.py",
    "boot/test_ipad_console.py",
    "boot/test_ipad_shell.py",
    "boot/test_load_linux_diagnostic.py",
    "boot/test_load_m1n1.py",
    "boot/test_t7001_entry_marker.py",
    "boot/test_t7001_memory_size.py",
    "boot/test_t7001_reserved_memory.py",
    "kernel/test_hdq_uart_patch.py",
    "kernel/test_spi_s5l_patch.py",
    "tools/test_check_offline.py",
)


@dataclass
class Outcome:
    name: str
    state: str
    detail: str = ""


def execute(name: str, arguments: list[str], timeout: float) -> Outcome:
    env = dict(os.environ)
    # Existing scripts use asserts; PYTHONOPTIMIZE must not disable checks.
    env.pop("PYTHONOPTIMIZE", None)
    try:
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Outcome(name, "FAIL", f"host test exceeded {timeout:g}s")
    except OSError as error:
        return Outcome(name, "FAIL", str(error))
    return Outcome(name, "PASS" if result.returncode == 0 else "FAIL",
                   (result.stdout + result.stderr).strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="local exact pinned Hoolock pcie.c; enables two native harnesses")
    parser.add_argument("--z2-source", type=Path, help="local exact pinned apple_z2.c; enables touchscreen harness")
    parser.add_argument("--openiboot-source", type=Path, help="local exact pinned multitouch-z2.c; enables legacy comparison harness")
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true", help="enable ASan/UBSan for requested native harnesses")
    parser.add_argument("--usb-control", type=Path, help="built control payload directory")
    parser.add_argument("--usb-diagnostic", type=Path, help="built USB diagnostic payload directory")
    parser.add_argument("--timeout", type=float, default=60, help="per host-test limit in seconds")
    parser.add_argument("--require-all", action="store_true", help="also fail if any optional check is skipped")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        parser.error("--timeout must be positive and at most 3600 seconds")
    if args.sanitize and not (args.source or args.z2_source or args.openiboot_source):
        parser.error("--sanitize requires --source, --z2-source or --openiboot-source")
    if bool(args.usb_control) != bool(args.usb_diagnostic):
        parser.error("supply both --usb-control and --usb-diagnostic")
    for path in (args.source, args.z2_source, args.openiboot_source):
        if path and not path.is_file():
            parser.error("source arguments must be existing files")
    for path in (args.usb_control, args.usb_diagnostic):
        if path and not path.is_dir():
            parser.error("USB payload arguments must be existing directories")

    outcomes = [execute(name, [name], args.timeout) for name in HOST_TESTS]
    image_test = "boot/test_t7001_pongo_diagnostic.py"
    if (ROOT / "result-kernel/Image").is_file():
        outcomes.append(execute(image_test, [image_test], args.timeout))
    else:
        outcomes.append(Outcome(image_test, "SKIP", "requires result-kernel/Image"))
    usb_test = "boot/test_usb_diagnostic.py"
    if args.usb_control:
        outcomes.append(execute(usb_test, [usb_test, str(args.usb_control.resolve()),
                                         str(args.usb_diagnostic.resolve())], args.timeout))
    else:
        outcomes.append(Outcome(usb_test, "SKIP", "requires both built USB payload directories"))
    native = (("kernel/test_brcmfmac_otp_patch.py", args.source, "--source (pcie.c)"),
              ("kernel/test_brcmfmac_otp_parser.py", args.source, "--source (pcie.c)"),
              ("kernel/test_apple_z2_receive.py", args.z2_source, "--z2-source (apple_z2.c)"),
              ("kernel/test_openiboot_z2_reference.py", args.openiboot_source, "--openiboot-source (multitouch-z2.c)"))
    for name, source, requirement in native:
        if not source:
            outcomes.append(Outcome(name, "SKIP", "requires exact pinned " + requirement))
        elif not shutil.which(args.cc) or not shutil.which("patch"):
            # Explicitly requested checks cannot silently become optional skips.
            outcomes.append(Outcome(name, "FAIL", "requested native check requires compiler and patch"))
        else:
            arguments = [name, "--source", str(source.resolve()), "--cc", args.cc]
            if args.sanitize:
                arguments.append("--sanitize")
            outcomes.append(execute(name, arguments, args.timeout))
    for result in outcomes:
        print(f"{result.state}: {result.name}")
        if result.detail and (args.verbose or result.state != "PASS"):
            print(result.detail)
    counts = {state: sum(o.state == state for o in outcomes) for state in ("PASS", "FAIL", "SKIP")}
    print(f"Offline checks: {counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    return int(bool(counts["FAIL"] or (args.require_all and counts["SKIP"])))


if __name__ == "__main__":
    raise SystemExit(main())
