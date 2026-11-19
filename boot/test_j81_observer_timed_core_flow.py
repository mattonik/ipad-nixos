"""Scripted-console test of the timed GPC request plus immediate core-ID read. No device connection is opened."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_observer_paired_campaign as campaign

_source = (Path(__file__).parent / "test_j81_observer_paired_flow.py").read_text()
exec(_source[_source.index("BOOT = "):_source.index("def run(job")])  # helpers only: BOOT, SHA, FILES, Console, words
BEFORE = ["stage=before-miscacg-write address=0x20e032000", "old=0x00000000"]
AFTER = ["new=0x00000001", "stage=after-miscacg-write"]


def timed_console(scenario):
    lines = ["stage=before-watchdog-open", "stage=watchdog-armed timeout=20"]
    if scenario == "gate-skip":
        lines += ["stage=before-pmgr-read address=0x20e020320 width=32", "stage=after-pmgr-read raw=0x000003ff",
                  "stage=before-miscacg-read address=0x20e032000 width=32", "stage=after-miscacg-read raw=0x00000000",
                  "stage=skipped reason=miscacg-not-1", "stage=finished rc=0", "stage=watchdog-disarmed"]
        return Console(lines)
    values = {"pmgr-read": 0x3ff, "miscacg-read": 1, "gpc-state": 0}
    for name, address in campaign.CORE_STAGES[:3]:
        if scenario == "reordered" and name == "miscacg-read":
            address = "0x20e005004"
        lines += [f"stage=before-{name} address={address} width=32", f"stage=after-{name} raw=0x{values[name]:08x}"]
    lines += ["stage=before-timed-sequence address=0x201000020 width=32", "checkpoint=before-gpc-writes",
              "checkpoint=gpc-poll-ok-polls-page5 a=0x0000000b b=0x40000000", "checkpoint=ticks-poll-to-core-read a=0x00000400 b=0x00000000"]
    if scenario == "hang":
        return Console(lines)  # silence after the core-read checkpoint
    lines += ["stage=after-timed-sequence raw=0x00070500", "stage=finished rc=0", "stage=watchdog-disarmed"]
    return Console(lines)


def run(job, scenario=None):
    path = job / (scenario or "success")
    cycle = Console([
        "stage=before-pmgr-read address=0x20e020320 width=32",
        "stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0",
        f"stage=before-pmgr-cycle module={SHA} kernel_notes={campaign.NOTES}", "stage=after-pmgr-cycle rc=0"])
    core = timed_console(scenario)
    sockets = [cycle, words(0), Console([]), words(0), Console(BEFORE + AFTER), words(1), core, words(1)]
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
        replace(campaign, "time", new=type("T", (), {"monotonic": staticmethod(iter(range(0, 10**6, 1)).__next__), "sleep": staticmethod(lambda s: None)})) if scenario == "hang" else None
        replace(campaign.bridge, "capture")
        replace(campaign.socket, "create_connection", side_effect=sockets)
        try:
            campaign.run(path)
        except RuntimeError as error:
            assert scenario in ("reordered", "hang"), f"unexpected stop in {scenario}: {error}"
        else:
            assert scenario not in ("reordered", "hang"), f"{scenario} accepted"
    assert (path / "summary-before-timed.txt").exists(), "partial summary must be on disk before the timed step"
    result = (path / "timed-core-result.txt").read_text()
    if scenario in ("reordered", "hang"):
        assert "no result" in result and not (path / "summary.txt").exists()
        if scenario == "reordered":
            assert b"FEED 2\n" not in core.commands, "no feed after an unexpected checkpoint"
        else:
            assert b"FEED 3\n" in core.commands and b"FEED 4\n" not in core.commands
    elif scenario == "gate-skip":
        assert "'skipped': 'miscacg-not-1'" in result and "timed-sequence" not in result
    else:
        assert "'timed-sequence': 460032" in result  # 0x00070500
        assert b"--core-revision-cycle " + campaign.CORE_TOOL_SHA.encode() in core.commands[0]
        assert b"FEED 4\n" in core.commands and (path / "summary.txt").exists()


with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "gfx-bridge-plan.bin").write_bytes(b"fixture for mocked bridge only")
    for scenario in (None, "gate-skip", "reordered", "hang"):
        run(root, scenario)
print("PASS: timed GPC + core read: full read, gate skip, no feed after an unexpected checkpoint, hang leaves no result")
