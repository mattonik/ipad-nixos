"""Scripted-console test of the gated core-ID step (after the MiscACG write, the guarded +0x2d000 write and the paired GPC batch). No device connection is opened."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_observer_paired_campaign as campaign

_source = (Path(__file__).parent / "test_j81_observer_paired_flow.py").read_text()
exec(_source[_source.index("BOOT = "):_source.index("def run(job")])  # helpers only: BOOT, SHA, PAIRED, FILES, Console, words
BEFORE = ["stage=before-miscacg-write address=0x20e032000", "old=0x00000000"]
AFTER = ["new=0x00000001", "stage=after-miscacg-write"]
TBEFORE = ["stage=before-tvm-write address=0x20e02d000", "old=0x00000000"]
TAFTER = ["new=0x00000001", "stage=after-tvm-write"]


def core_console(scenario):
    names = campaign.CORE_STAGES
    values = {"pmgr-read": 0x3ff, "tvm-unused": 0, "miscacg-read": 1, "page5-read": 0x40000000, "gpc-state": 1,
              "gpc-control": 0x40000000, "gpu-revision": 0x00070500}
    lines = ["stage=before-watchdog-open", "stage=watchdog-armed timeout=20"]
    if scenario == "skipped":
        values["page5-read"] = 0
    for i, (name, address) in enumerate(names):
        if scenario == "reordered" and i == 1:
            name, address = names[2]
        lines += [f"stage=before-{name} address={address} width=32", f"stage=after-{name} raw=0x{values[name]:08x}"]
        if scenario == "skipped" and name == "page5-read":
            lines += ["stage=skipped reason=page5-bit30-clear"]
            break
    lines += ["stage=finished rc=0", "stage=watchdog-disarmed"]
    return Console(lines)


def run(job, scenario=None):
    fault = scenario in ("tvm-refused", "tvm-b3-zero")
    path = job / (scenario or "success")
    cycle = Console([
        "stage=before-pmgr-read address=0x20e020320 width=32",
        "stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0",
        f"stage=before-pmgr-cycle module={SHA} kernel_notes={campaign.NOTES}", "stage=after-pmgr-cycle rc=0"])
    kpoll = Console([
        "stage=before-watchdog-open", "stage=watchdog-armed timeout=20",
        "stage=before-pmgr-read address=0x20e020320 width=32",
        "stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0",
        "stage=before-gpc-state address=0x201e01000 width=32", "stage=after-gpc-state raw=0x00000000",
        "stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=paired",
        "checkpoint=before-kernel-batch", "checkpoint=kernel-batch " + PAIRED,
        "stage=after-gpc-page5-kpoll " + PAIRED, "stage=finished rc=0", "stage=watchdog-disarmed"])
    core = core_console(scenario)
    twriter = Console({"tvm-refused": ["stage=tvm-skipped pre-value-not-zero"]}.get(scenario, TBEFORE + TAFTER))
    b3 = words(1, tvm=0 if scenario == "tvm-b3-zero" else 1)
    sockets = [cycle, words(0), Console([]), words(0), Console(BEFORE + AFTER), words(1), twriter, b3, kpoll, words(1, tvm=1), core]
    with ExitStack() as stack:
        def replace(obj, name, **options):
            return stack.enter_context(patch.object(obj, name, **options))
        replace(campaign, "BUNDLE", new=job)
        replace(campaign, "manifest", return_value=FILES)
        replace(campaign, "stage_all")
        replace(campaign, "stage")
        replace(campaign, "WRITER_SHA", new=campaign.hashlib.sha256(campaign.WRITER.read_bytes()).hexdigest())
        replace(campaign, "TVM_WRITER_SHA", new=campaign.hashlib.sha256(campaign.TVM_WRITER.read_bytes()).hexdigest())
        replace(campaign, "shell", side_effect=lambda command, timeout=8: b"TVM_WRITER_OK/ #" if "TVM_WRITER_OK" in command else b"WRITER_OK/ #" if "WRITER_OK" in command else b"gfx-request pid=1")
        replace(campaign, "boot_id", return_value=BOOT)
        replace(campaign, "preflight", return_value=BOOT)
        replace(campaign.bridge, "capture")
        connect = replace(campaign.socket, "create_connection", side_effect=sockets)
        try:
            campaign.run(path)
        except RuntimeError:
            assert scenario in ("reordered", "tvm-refused", "tvm-b3-zero"), "unexpected stop"
        else:
            assert scenario not in ("reordered", "tvm-refused", "tvm-b3-zero"), "unsafe scenario accepted"
    if fault:
        assert not (path / "kpoll.log").exists() and not (path / "snapshot-c.log").exists(), "GPC batch must not start after a failed +0x2d000 step"
        assert not (path / "summary.txt").exists() and not (path / "core-id.log").exists()
        assert connect.call_count == (7 if scenario == "tvm-refused" else 8), connect.call_count
        return
    assert (path / "summary.txt").exists(), "summary must be on disk before the core read"
    summary = (path / "summary.txt").read_text()
    assert "tvm 0x2d000 A=0x00000000 B=0x00000000 B2=0x00000000 B3=0x00000001 C=0x00000001" in summary, summary
    assert "tvm-write={'old': 0, 'new': 1}" in summary
    result = (path / "core-id-result.txt").read_text()
    if scenario == "reordered":
        assert "no result" in result and b"FEED 2\n" not in core.commands, "no feed after an unexpected checkpoint"
    elif scenario == "skipped":
        assert "'skipped': 'page5-bit30-clear'" in result and "gpu-revision" not in result
        assert b"FEED 3\n" in core.commands and b"FEED 4\n" not in core.commands
    else:
        assert "'gpu-revision': 460032" in result  # 0x00070500
        assert core.commands[0].startswith(b'test "$(sha256sum /tmp/gpu-watchdog-supervisor')
        assert b"--core-revision-cycle " + campaign.CORE_TOOL_SHA.encode() in core.commands[0]
        assert b"FEED 6\n" in core.commands


with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "gfx-bridge-plan.bin").write_bytes(b"fixture for mocked bridge only")
    for scenario in (None, "skipped", "reordered", "tvm-refused", "tvm-b3-zero"):
        run(root, scenario)
print("PASS: guarded +0x2d000 write between B2 and B3; any failure stops before GPC; core-ID gating unchanged")
