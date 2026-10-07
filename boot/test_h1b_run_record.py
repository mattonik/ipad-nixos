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

READONLY_PREFIXES = ("cat ", "uname", "dmesg", "lspci", "od ", "ls ")


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


def main():
    # Decoder and classifier.
    msi = R.msi_readback("000000 05 00 89 00 00 f0 ff bf 00 00 00 00 08 00 00 00\n000010\n")
    assert msi == {"cap_id_next": 5, "control": 0x89, "address_lo": 0xBFFFF000, "address_hi": 0, "data": 8}, msi
    assert R.msi_readback("garbage") is None
    cl = R.classify("[1] apple-dart: DART error SID 3\n[2] brcmfmac: Direct firmware load for x failed with error -2\n[3] wlan0: x\n")
    assert cl["dart_fault"]["count"] == 1 and cl["fw_load_failed"]["count"] == 1 and cl["interface_created"]["count"] == 1
    # Every command is read-only.
    assert all(c.startswith(READONLY_PREFIXES) for _, c in R.COMMANDS), R.COMMANDS
    for _, c in R.COMMANDS:
        assert not any(w in c for w in (" > ", "echo ", "ip ", "iw ", "ifconfig", "modprobe", "insmod", "dd ", "setpci", "wpa", "rm ", "mount")), c
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
