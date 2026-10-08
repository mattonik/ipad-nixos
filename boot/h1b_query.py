#!/usr/bin/env python3
"""On-demand read-only queries against a held Wi-Fi H1B device (patch 0071), without building a new payload.

Usage: python3 boot/h1b_query.py PRIVATE_PAYLOAD_DIR [--default] [COMMAND ...]

COMMAND is one of (quote it): "tcm 0x1dd6c8 104" (absolute ARM address inside the RAM) | "core pcie2 0x48 8" | "core cc 0x58 24" |
shared | rings | console | snap | diff | arm
With --allow-rom also: "unlock rom" then "rom 0x0 256" (addresses below the RAM base; the driver refuses without the unlock).
--default runs: shared, core cc 0x58 24 (GPIO block), core pcie2 0x48 8 (mailbox int/mask), console, rings.
`core` reads are limited by the driver to a safe-register list (a PCIe2 sweep 0x0-0xff rebooted the iPad in run 12).
`core` reads need the payload booted with brcmfmac.h1b_hold=1 (otherwise the driver answers with an error).

Connects to the debug shell, mounts debugfs (kernel files only), then for each command writes it to
/sys/kernel/debug/brcmfmac-h1b/query and reads .../result. Results go to PRIVATE_PAYLOAD_DIR/queries-<UTC>/ (0700, 0600,
Git-ignored). Nothing is written to the device other than the query text itself.
"""
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NUM = r"(?:0x[0-9a-fA-F]+|[0-9]+)"
ALLOWED = (rf"tcm {NUM} {NUM}", rf"core (?:pcie2|cc) {NUM} {NUM}", r"shared", r"rings", r"console", r"snap", r"diff", r"arm")
ROM = (r"unlock rom", rf"rom {NUM} {NUM}")
DEFAULT = ("shared", "core cc 0x58 24", "core pcie2 0x48 8", "console", "rings")
DIR = "/sys/kernel/debug/brcmfmac-h1b"


def validate(command, allow_rom=False):
    patterns = ALLOWED + (ROM if allow_rom else ())
    if not any(re.fullmatch(p, command) for p in patterns):
        hint = " (ROM reads need --allow-rom)" if any(re.fullmatch(p, command) for p in ROM) else ""
        raise ValueError(f"not an allowed query: {command!r}{hint}")
    return command


def run_queries(shell, payload_dir, commands, now=None, allow_rom=False):
    commands = [validate(c, allow_rom) for c in commands]
    out = Path(payload_dir).resolve() / ("queries-" + (now or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    out.mkdir(mode=0o700)
    shell.run("mountpoint -q /sys/kernel/debug || mount -t debugfs none /sys/kernel/debug", timeout=20, check=False)
    results = []
    for i, command in enumerate(commands):
        text = shell.run(f'echo "{command}" > {DIR}/query && cat {DIR}/result', timeout=60, check=False)
        fd = os.open(out / f"query-{i:02d}.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"# {command}\n{text}")
        results.append((command, text))
    return out, results


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("payload_dir")
    ap.add_argument("--default", action="store_true")
    ap.add_argument("--allow-rom", action="store_true", help="also accept: unlock rom, rom OFF LEN (a deliberate second step)")
    ap.add_argument("commands", nargs="*")
    args = ap.parse_args(argv[1:])
    commands = list(args.commands) + (list(DEFAULT) if args.default or not args.commands else [])
    from ipad_console import IPadShell
    from session_evidence import SessionEvidence
    payload = Path(args.payload_dir)
    shell = IPadShell(evidence=SessionEvidence([f"payload={payload / 'm1n1-linux.bin'}"]))
    shell.connect()
    out, results = run_queries(shell, payload, commands, allow_rom=args.allow_rom)
    print("query results:", out)
    for command, text in results:
        print(f"--- {command}: {len(text.splitlines())} lines" + ("  (ERROR)" if "error:" in text else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
