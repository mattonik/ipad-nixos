#!/usr/bin/env python3
"""Read-only post-boot evidence capture for the Wi-Fi H1B run (matrix: research/2026-10-07-wifi-h1b-evidence-matrix.md).

Usage: python3 boot/h1b_run_record.py PRIVATE_PAYLOAD_DIR [--watch SECONDS] [--interval SECONDS]

--watch samples while brcmfmac is bound (before it tears itself down on failure): one read-only shell command per
sample returns the device uptime, the brcmfmac/MSI lines of /proc/interrupts, the endpoint MSI capability bytes
and whether brcmfmac has been removed; samples go to watch.jsonl. It stops at the removal or after SECONDS, then
the normal record is taken.

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


# One read-only command per watch sample (cut/grep/od/printf/echo only).
WATCH_COMMAND = ("printf 'UP '; cut -d' ' -f1 /proc/uptime; echo INT; grep -i 'brcmf\\|msi' /proc/interrupts; echo MSI; "
                 "od -A x -t x1 -j 0x58 -N 16 /sys/bus/pci/devices/0000:01:00.0/config 2>&1; echo REMOVED; "
                 "dmesg | grep -c brcmf_pcie_remove; echo END")


def parse_sample(text):
    """Split a WATCH_COMMAND reply into uptime, interrupt lines, decoded MSI capability and a removed flag."""
    sections, current = {"UP": [], "INT": [], "MSI": [], "REMOVED": []}, "UP"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("UP "):
            sections["UP"].append(stripped[3:])
        elif stripped in ("INT", "MSI", "REMOVED"):
            current = stripped
        elif stripped == "END":
            break
        elif stripped:
            sections[current].append(stripped)
    try:
        uptime = float(sections["UP"][0])
    except (IndexError, ValueError):
        uptime = None
    removed = bool(sections["REMOVED"]) and sections["REMOVED"][-1].isdigit() and int(sections["REMOVED"][-1]) > 0
    return {"uptime": uptime, "interrupts": sections["INT"], "msi": msi_readback("\n".join(sections["MSI"])),
            "removed": removed}


def watch(shell, out, seconds, interval, clock=time.monotonic, sleep=time.sleep):
    """Sample until brcmfmac is removed or `seconds` pass; returns the samples (also written to watch.jsonl)."""
    samples, start = [], clock()
    fd = os.open(out / "watch.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        while clock() - start < seconds:
            sample = parse_sample(shell.run(WATCH_COMMAND, timeout=20, check=False))
            sample["host_t"] = round(clock() - start, 2)
            samples.append(sample)
            f.write(json.dumps(sample) + "\n")
            f.flush()
            if sample["removed"]:
                break
            sleep(interval)
    return samples


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


def watch_summary(samples):
    """Peak interrupt count of the brcmfmac line and the last MSI capability seen while the driver was bound."""
    if not samples:
        return None
    enabled = [x for x in samples if x["msi"] and x["msi"]["address_lo"]]
    counts = []
    for x in samples:
        for line in x["interrupts"]:
            parts = line.split()
            if parts and parts[0].rstrip(":").isdigit() and "brcm" in line.lower():
                counts.append((x["host_t"], sum(int(v) for v in parts[1:4] if v.isdigit()), " ".join(parts[4:])[:80]))
    return {"samples": len(samples), "driver_removed_seen": any(x["removed"] for x in samples),
            "msi_seen_enabled": bool(enabled), "last_enabled_msi": enabled[-1]["msi"] if enabled else None,
            "brcmf_irq_max_count": max((c[1] for c in counts), default=0),
            "brcmf_irq_line": counts[-1][2] if counts else None}


def record(shell, payload_dir, now=None, watch_seconds=0, interval=1.0, clock=time.monotonic, sleep=time.sleep):
    payload_dir = Path(payload_dir).resolve()
    manifest = json.loads((payload_dir / "PRIVATE_MANIFEST.json").read_text())
    out = payload_dir / ("run-" + (now or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    out.mkdir(mode=0o700)
    samples = watch(shell, out, watch_seconds, interval, clock, sleep) if watch_seconds else []
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
        "watch": watch_summary(samples),
    }
    fd = os.open(out / "summary.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(summary, f, indent=2)
    return out, summary


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("payload_dir")
    ap.add_argument("--watch", type=float, default=0, help="sample for up to this many seconds while brcmfmac is bound")
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args(argv[1:])
    from ipad_console import IPadShell
    from session_evidence import SessionEvidence
    payload = Path(args.payload_dir)
    shell = IPadShell(evidence=SessionEvidence([f"payload={payload / 'm1n1-linux.bin'}"]))
    shell.connect()
    out, summary = record(shell, payload, watch_seconds=args.watch, interval=args.interval)
    print("run directory:", out)
    print("identity:", summary["identity"])
    print("msi capability (final):", summary["msi_capability"])
    if summary["watch"]:
        print("watch:", json.dumps(summary["watch"]))
    for label, info in summary["classes"].items():
        print(f"  {label}: {info['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
