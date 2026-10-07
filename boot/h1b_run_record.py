#!/usr/bin/env python3
"""Read-only post-boot evidence capture for the Wi-Fi H1B run (matrix: research/2026-10-07-wifi-h1b-evidence-matrix.md).

Usage: python3 boot/h1b_run_record.py PRIVATE_PAYLOAD_DIR

Connects to the debug shell (telnet 172.16.42.1), runs ONLY read-only commands (cat, dmesg, od on PCI
config space, ls) and stores the raw output under PRIVATE_PAYLOAD_DIR/run-<UTC>/ (mode 0600, ignored by
Git). It never writes a device register, brings an interface up, scans, or loads anything. It records:

  * /proc/cmdline and whether it carries the payload's run token (device-side identity);
  * the whole dmesg, with a classifier summary of the evidence classes below;
  * the endpoint MSI capability readback (config offsets 0x58..0x67), /proc/interrupts, the PCI/IOMMU state;
  * wlan interface presence (creation is allowed; scanning/association is never started here).

The classifier only labels what the log shows; the verdict is the reviewer's (matrix in the research note).
"""
import json
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

COMMANDS = [
    ("cmdline", "cat /proc/cmdline"),
    ("uname", "uname -a"),
    ("dmesg", "dmesg"),
    ("interrupts", "cat /proc/interrupts"),
    ("lspci", "lspci -nn"),
    ("msi_cap", "od -A x -t x1 -j 0x58 -N 16 /sys/bus/pci/devices/0000:01:00.0/config"),
    ("pci_cmd", "od -A x -t x1 -j 0x04 -N 4 /sys/bus/pci/devices/0000:01:00.0/config"),
    ("iommu_group", "ls -l /sys/bus/pci/devices/0000:01:00.0/iommu_group"),
    ("net", "ls /sys/class/net"),
    ("firmware_files", "ls -l /lib/firmware/brcm"),
]

# (label, regex over dmesg lines) -> evidence class names from the matrix.
CLASSES = [
    ("fw_request_start", r"brcmf.*(Direct firmware load|firmware|FWCON|PCIe)"),
    ("fw_load_failed", r"(Direct firmware load for .* failed|brcmf.*firmware.*(fail|error|-2\b))"),
    ("nvram_empty_or_missing", r"brcmf.*(nvram|NVRAM).*(empty|invalid|fail|error)"),
    ("dart_fault", r"(apple-dart|DART).*(error|fault|exception|SID)"),
    ("msi_error", r"(MSI_ERR|MSI_BAD_DATA|msi.*(error|bad))"),
    ("firmware_halt_or_timeout", r"brcmf.*(halt|trap|timeout|timed out|no response|dongle|reset)"),
    ("brcmf_msgbuf_pcie_activity", r"brcmf.*(msgbuf|MSGBUF|ring|D2H|H2D|ioctl|cur_etheraddr|ver)"),
    ("interface_created", r"(wlan0|wlan\d+)"),
    ("scan_or_assoc", r"(scan|SCAN|assoc|ASSOC|connect|CONN)"),
    ("tx", r"(brcmf.*TX|xmit)"),
]


def classify(dmesg):
    out = {}
    for label, pattern in CLASSES:
        rx = re.compile(pattern)
        hits = [l for l in dmesg.splitlines() if rx.search(l)]
        out[label] = {"count": len(hits), "first": hits[:3]}
    return out


def msi_readback(od_output):
    """Decode `od -A x -t x1` of config 0x58..0x67 to (control, address hi/lo, data) - little endian."""
    nums = []
    for line in od_output.splitlines():
        parts = line.split()
        if parts and re.fullmatch(r"[0-9a-fA-F]{6}", parts[0]):
            nums += [int(x, 16) for x in parts[1:]]
    if len(nums) < 16:
        return None
    b = nums[:16]
    word = lambda o, n: int.from_bytes(bytes(b[o:o + n]), "little")
    return {"cap_id_next": word(0, 2), "control": word(2, 2), "address_lo": word(4, 4), "address_hi": word(8, 4),
            "data": word(12, 2)}


def record(shell, payload_dir, now=None):
    payload_dir = Path(payload_dir).resolve()
    manifest = json.loads((payload_dir / "PRIVATE_MANIFEST.json").read_text())
    out = payload_dir / ("run-" + (now or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    out.mkdir(mode=0o700)
    raw = {}
    for name, command in COMMANDS:
        raw[name] = shell.run(command, timeout=60 if name == "dmesg" else 20, check=False)
        fd = os.open(out / f"{name}.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(raw[name])
    token_ok = f"j81.run_id={manifest['run_id']}" in raw["cmdline"]
    msi = msi_readback(raw["msi_cap"])
    summary = {
        "run_id": manifest["run_id"], "token_matches_cmdline": token_ok,
        "identity": "device_token_observed" if token_ok else "handoff_only (token not seen)",
        "msi_capability": msi,
        "msi_expected": {"address": "0x00000000bffff000", "data": "8..15 (slot 8 first)", "aic_line": "232 for slot 8"},
        "classes": classify(raw["dmesg"]),
    }
    fd = os.open(out / "summary.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(summary, f, indent=2)
    return out, summary


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    from ipad_console import IPadShell
    from session_evidence import SessionEvidence
    payload = Path(argv[1])
    shell = IPadShell(evidence=SessionEvidence([f"payload={payload / 'm1n1-linux.bin'}"]))
    shell.connect()
    out, summary = record(shell, payload)
    print("run directory:", out)
    print("identity:", summary["identity"])
    print("msi capability:", summary["msi_capability"])
    for label, info in summary["classes"].items():
        print(f"  {label}: {info['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
