"""Scripted-console test of the guarded MiscACG write step. No device connection is opened."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_observer_paired_campaign as campaign
_source = (Path(__file__).parent / "test_j81_observer_paired_flow.py").read_text()
exec(_source[_source.index("BOOT = "):_source.index("def run(job")])  # helpers only: BOOT, SHA, PAIRED, FILES, Console, words

BEFORE = ["stage=before-miscacg-write address=0x20e032000", "old=0x00000000"]
AFTER = ["new=0x00000001", "stage=after-miscacg-write"]


def run(job, fault=None):
    path = job / (fault or "success")
    cycle = Console([
        "stage=before-pmgr-read address=0x20e020320 width=32",
        "stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0",
        f"stage=before-pmgr-cycle module={SHA} kernel_notes={campaign.NOTES}",
        "stage=after-pmgr-cycle rc=0",
    ])
    kpoll = Console([
        "stage=before-watchdog-open", "stage=watchdog-armed timeout=20",
        "stage=before-pmgr-read address=0x20e020320 width=32",
        "stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0",
        "stage=before-gpc-state address=0x201e01000 width=32", "stage=after-gpc-state raw=0x00000000",
        "stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=paired",
        "checkpoint=before-kernel-batch", "checkpoint=kernel-batch " + PAIRED,
        "stage=after-gpc-page5-kpoll " + PAIRED, "stage=finished rc=0", "stage=watchdog-disarmed",
    ])
    writer = Console({"refused": ["stage=miscacg-skipped pre-value-not-zero"]}.get(fault, BEFORE + AFTER))
    a, b = words(0), words(0)
    b2 = words(0 if fault == "post-write-zero" else 1)
    c = words(1)
    sockets = [cycle, a, Console([]), b, writer, b2, kpoll, c]
    with ExitStack() as stack:
        def replace(obj, name, **options):
            return stack.enter_context(patch.object(obj, name, **options))
        replace(campaign, "BUNDLE", new=job)
        replace(campaign, "manifest", return_value=FILES)
        replace(campaign, "stage_all")
        replace(campaign, "stage")
        replace(campaign, "WRITER_SHA", new=campaign.hashlib.sha256(campaign.WRITER.read_bytes()).hexdigest())
        replace(campaign, "shell", side_effect=lambda command, timeout=8: b"WRITER_OK/ #" if "WRITER_OK" in command else b"gfx-request pid=1")
        replace(campaign, "boot_id", return_value=BOOT)
        replace(campaign, "preflight", return_value=BOOT)
        replace(campaign.bridge, "capture")
        connect = replace(campaign.socket, "create_connection", side_effect=sockets)
        try:
            campaign.run(path)
        except RuntimeError:
            assert fault, "unexpected stop"
        else:
            assert fault is None, f"{fault} accepted"
    if fault:
        assert not (path / "summary.txt").exists() and not (path / "snapshot-c.log").exists()
        assert not (path / "kpoll.log").exists(), "GPC batch must not start after a failed write step"
        assert connect.call_count == (5 if fault == "refused" else 6)
        return
    assert connect.call_count == 8
    assert b"WRITE\n" in writer.commands and writer.commands[0].startswith(b"chmod +x /tmp/pmgr-miscacg-set")
    summary = (path / "summary.txt").read_text()
    assert "miscacg-write={'old': 0, 'new': 1}" in summary and "pre-gpc MiscACG=0x00000001 bit0=1 (after" in summary


with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "gfx-bridge-plan.bin").write_bytes(b"fixture for mocked bridge only")
    for scenario in (None, "refused", "post-write-zero"):
        run(root, scenario)
print("PASS: guarded MiscACG write step runs between snapshots B and B2, and any failure stops before GPC")
