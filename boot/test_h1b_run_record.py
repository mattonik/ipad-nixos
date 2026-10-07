#!/usr/bin/env python3
"""Host test for boot/h1b_run_record.py with a fake shell (no device)."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import h1b_run_record as R  # noqa: E402

READONLY_PREFIXES = ("cat ", "uname", "dmesg", "lspci", "od ", "ls ", "mountpoint -q /sys/kernel/debug")


class FakeShell:
    def __init__(self, token, ok=True):
        self.commands = []
        self.token = token
        self.ok = ok

    def run(self, command, timeout=10, check=True):
        self.commands.append(command)
        if command == "cat /proc/cmdline":
            return f"console=tty0 j81.run_id={self.token}\n" if self.ok else "console=tty0\n"
        if command == "dmesg":
            return ("[0.5] brcmfmac: Direct firmware load for brcm/brcmfmac4350c2-pcie.bin\n"
                    "[0.6] apple-dart 602002000.iommu: DART error SID 1\n[0.7] brcmf_pcie: ring D2H ready\n")
        if "-j 0x58" in command:
            return "000000 05 00 89 00 00 f0 ff bf 00 00 00 00 08 00 00 00\n000010\n"
        return ""


def watch_reply(up, irq, msi_hex, removed):
    return (f"UP {up}\nINT\n" + (f" 55:   0   {irq}   0  AIC  65700 Level  brcmf_pcie_intr\n" if irq is not None else "") +
            "MSI\n" + (f"000000 05 00 89 00 {msi_hex}\n000010\n" if msi_hex else "") + f"REMOVED\n{removed}\nEND\n")


class WatchShell:
    """Replays scripted watch replies; the last one reports brcmfmac removed."""
    def __init__(self, replies):
        self.replies, self.commands = list(replies), []

    def run(self, command, timeout=10, check=True):
        self.commands.append(command)
        return self.replies.pop(0) if self.replies else watch_reply(99.0, None, "", 1)


def main():
    # Watch parsing: a bound driver with an interrupt, then removal.
    s = R.parse_sample(watch_reply(61.5, 3, "00 f0 ff bf 00 00 00 00 08 00 00 00", 0))
    assert s["uptime"] == 61.5 and not s["removed"] and s["msi"]["address_lo"] == 0xBFFFF000 and s["msi"]["data"] == 8
    assert any("brcmf_pcie_intr" in l for l in s["interrupts"])
    assert R.parse_sample(watch_reply(70.0, None, "", 1))["removed"] and R.parse_sample("garbage")["uptime"] is None
    # The watch command itself is read-only.
    cmd = R.WATCH_COMMAND
    for token in ("cut -d", "grep -i", "od -A x", "dmesg | grep -c"):
        assert token in cmd
    for bad in (" > ", ">>", "echo 1", "rm ", "ip ", "iw ", "ifconfig", "modprobe", "setpci", "dd ", "mount", "wpa", "tee"):
        assert bad not in cmd.replace("2>&1", ""), bad
    # Decoder and classifier.
    msi = R.msi_readback("000000 05 00 89 00 00 f0 ff bf 00 00 00 00 08 00 00 00\n000010\n")
    assert msi == {"cap_id_next": 5, "control": 0x89, "address_lo": 0xBFFFF000, "address_hi": 0, "data": 8}, msi
    assert R.msi_readback("garbage") is None
    cl = R.classify("[1] apple-dart: DART error SID 3\n[2] brcmfmac: Direct firmware load for x failed with error -2\n[3] wlan0: x\n")
    assert cl["dart_fault"]["count"] == 1 and cl["fw_load_failed"]["count"] == 1 and cl["interface_created"]["count"] == 1
    # Every command is read-only.
    assert all(c.startswith(READONLY_PREFIXES) for _, c in R.COMMANDS), R.COMMANDS
    MOUNT = "mountpoint -q /sys/kernel/debug && echo mounted || mount -t debugfs none /sys/kernel/debug"
    assert R.COMMANDS[0] == ("debugfs_mount", MOUNT), "the only non-read command is the fixed debugfs mount"
    for _, c in R.COMMANDS[1:]:
        assert not any(w in c for w in (" > ", "echo ", "ip ", "iw ", "ifconfig", "modprobe", "insmod", "dd ", "setpci", "wpa", "rm ")), c
        assert "mount" not in c, c
    # End to end against a fake payload directory and fake shell.
    d = Path(tempfile.mkdtemp(prefix="h1b-rec-"))
    try:
        (d / "PRIVATE_MANIFEST.json").write_text(json.dumps({"run_id": "ab" * 16}))
        shell = FakeShell("ab" * 16)
        out, summary = R.record(shell, d, now="T1")
        assert summary["token_matches_cmdline"] and summary["identity"] == "device_token_observed"
        assert summary["msi_capability"]["address_lo"] == 0xBFFFF000 and summary["msi_capability"]["data"] == 8
        assert (out / "dmesg.txt").exists() and oct(os.stat(out / "dmesg.txt").st_mode & 0o777) == "0o600"
        assert oct(os.stat(out).st_mode & 0o777) == "0o700"
        assert [c for c in shell.commands] == [c for _, c in R.COMMANDS]
        # Wrong/missing token downgrades the identity claim.
        _, bad = R.record(FakeShell("ab" * 16, ok=False), d, now="T2")
        assert not bad["token_matches_cmdline"] and bad["identity"].startswith("handoff_only")
        # Watch mode: samples recorded until removal; summary holds the last enabled MSI capability and the peak count.
        ticks = iter(range(0, 1000))
        ws = WatchShell([watch_reply(60.0, 0, "00 f0 ff bf 00 00 00 00 08 00 00 00", 0),
                         watch_reply(61.0, 1, "00 f0 ff bf 00 00 00 00 08 00 00 00", 0),
                         watch_reply(62.0, 4, "00 f0 ff bf 00 00 00 00 08 00 00 00", 0),
                         watch_reply(64.0, None, "", 1)])
        # Reuse the fake dmesg shell for the final record, replaying watch replies first.
        class Both(FakeShell):
            def run(self, command, timeout=10, check=True):
                if command == R.WATCH_COMMAND:
                    return ws.run(command)
                return super().run(command, timeout, check)
        both = Both("ab" * 16)
        out3, sm3 = R.record(both, d, now="T3", watch_seconds=30, interval=0.0, clock=lambda: float(next(ticks)), sleep=lambda x: None)
        w = sm3["watch"]
        assert w["samples"] == 4 and w["driver_removed_seen"] and w["msi_seen_enabled"]
        assert w["last_enabled_msi"]["address_lo"] == 0xBFFFF000 and w["last_enabled_msi"]["data"] == 8
        assert w["brcmf_irq_max_count"] == 4, w
        assert len((out3 / "watch.jsonl").read_text().splitlines()) == 4 and ws.commands.count(R.WATCH_COMMAND) == 4
        assert oct(os.stat(out3 / "watch.jsonl").st_mode & 0o777) == "0o600"
        # Without --watch nothing is sampled.
        assert R.record(FakeShell("ab" * 16), d, now="T4")[1]["watch"] is None
        # A run directory is never overwritten.
        try:
            R.record(shell, d, now="T1")
            raise AssertionError("expected refusal")
        except FileExistsError:
            pass
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("PASS: H1B run-record capture (read-only commands, MSI decode, classifier, token identity, private files)")


if __name__ == "__main__":
    main()
