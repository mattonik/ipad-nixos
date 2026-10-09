#!/usr/bin/env python3
"""Read-only probes during the setup pauses of an H1B payload (h1b_step_s / h1b_bell_only), before the reset.

Usage: python3 boot/h1b_window_probe.py PRIVATE_PAYLOAD_DIR

Waits for the pause lines in the kernel log (the same dmesg the streamer reads), then, in the pause before attach (baseline) and right after
the doorbell-only test rings (post-bell), runs ONLY allowlisted read-only probes: the h1b query commands (shared, core pcie2 0x20/0x24/0x48/0x4c/0x140,
arm, snap/diff) and `cat` of the DART and T7000 port register files that patches 0066 provide. Results: PRIVATE_PAYLOAD_DIR/window-<UTC>/ (0700/0600, Git-ignored).
"""
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import h1b_query as Q  # noqa: E402

BASELINE = ["shared", "core pcie2 0x20 4", "core pcie2 0x24 4", "core pcie2 0x48 8", "core pcie2 0x140 8", "arm", "snap"]
POSTBELL = ["core pcie2 0x20 4", "core pcie2 0x24 4", "core pcie2 0x48 8", "core pcie2 0x140 8", "shared", "diff"]
FILES = {"dart_regs": "cat /sys/kernel/debug/apple-dart-*/regs 2>&1", "port1_regs": "cat /sys/kernel/debug/t7000-pcie/port1_regs 2>&1"}


def save(out, name, text):
    fd = os.open(out / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def probe(shell, out, tag, commands):
    for i, c in enumerate(commands):
        Q.validate(c)
        text = shell.run(f'echo "{c}" > {Q.DIR}/query && cat {Q.DIR}/result', timeout=60, check=False)
        save(out, f"{tag}-q{i:02d}.txt", f"# {c}\n{text}")
    for name, cmd in FILES.items():
        save(out, f"{tag}-{name}.txt", shell.run(cmd, timeout=30, check=False))


def wait_for(shell, pattern, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        text = shell.run("dmesg", timeout=15, check=False)
        if re.search(pattern, text):
            return True
        time.sleep(0.3)
    return False


def main(argv):
    from ipad_console import IPadShell
    from session_evidence import SessionEvidence
    payload = Path(argv[1])
    shell = IPadShell(evidence=SessionEvidence([f"payload={payload / 'm1n1-linux.bin'}"]))
    shell.connect()
    shell.run("mountpoint -q /sys/kernel/debug || mount -t debugfs none /sys/kernel/debug", timeout=20, check=False)
    out = payload / ("window-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    out.mkdir(mode=0o700)
    if wait_for(shell, r"step: interrupt request done, pausing", 400):
        probe(shell, out, "baseline", BASELINE)
        print("baseline taken")
    if wait_for(shell, r"bell-only test: ringing", 120):
        time.sleep(1.5)
        probe(shell, out, "postbell", POSTBELL)
        print("post-bell taken")
    print("results:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
