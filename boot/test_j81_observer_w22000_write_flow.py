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
P1B = ["stage=before-pll1-write address=0x20e001008", "old=0x80480348"]
P1A = ["new=0x40480348", "stage=after-pll1-write"]
P4B = ["stage=before-pll4-write address=0x20e004008", "old=0x88480348"]
P4A = ["new=0x48480348", "stage=after-pll4-write"]
N1, N4 = 0x40480348, 0x48480348
W22B = ["stage=before-w22000-write address=0x20e022000", "old=0x00000000"]
W22A = ["new=0x80000000", "stage=after-w22000-write"]
H = 0x80000000


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


FAULTS = {"pre-state": 1, "vm-bit": 3, "tvm-refused": 4, "pll-unexpected": 5, "pll1-refused": 6, "pll1-bad-readback": 7,
          "pll4-refused": 8, "pll4-bad-readback": 9, "w22-nonzero": 9, "w22-refused": 10, "w22-bad-readback": 11,
          "lost-after-cycle": 13, "lost-after-bridge": 15}


def run(job, scenario=None):
    fault = scenario in FAULTS
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
    mwriter = Console(BEFORE + AFTER)
    twriter = Console({"tvm-refused": ["stage=tvm-skipped pre-value-not-zero"]}.get(scenario, TBEFORE + TAFTER))
    p1w = Console({"pll1-refused": ["stage=pll1-skipped pre-value-not-expected"]}.get(scenario, P1B + P1A))
    p4w = Console({"pll4-refused": ["stage=pll4-skipped pre-value-not-expected"]}.get(scenario, P4B + P4A))
    w22w = Console({"w22-refused": ["stage=w22000-skipped pre-value-not-zero"]}.get(scenario, W22B + W22A))
    s0 = words(1 if scenario == "pre-state" else 0, gfx=0x300)
    s1 = words(1, gfx=0x300, v23000=0x100 if scenario == "vm-bit" else 1)
    s2 = words(1, tvm=1, gfx=0x300, w1=0x80480347 if scenario == "pll-unexpected" else 0x80480348)
    s3 = words(1, tvm=1, gfx=0x300, w1=0x80480348 if scenario == "pll1-bad-readback" else N1)
    s4 = words(1, tvm=1, gfx=0x300, w1=N1, w4=0x88480348 if scenario == "pll4-bad-readback" else N4, w22=0x1 if scenario == "w22-nonzero" else 0)
    s5 = words(1, tvm=1, gfx=0x300, w1=N1, w4=N4, w22=0 if scenario == "w22-bad-readback" else H)
    a = words(0 if scenario == "lost-after-cycle" else 1, tvm=1, w1=N1, w4=N4, w22=H)
    b = words(1, tvm=0 if scenario == "lost-after-bridge" else 1, w1=N1, w4=N4, w22=H)
    cfin = words(1, tvm=1, w1=N1, w4=N4, w22=H)
    sockets = [s0, mwriter, s1, twriter, s2, p1w, s3, p4w, s4, w22w, s5, cycle, a, Console([]), b, kpoll, cfin, core]
    with ExitStack() as stack:
        def replace(obj, name, **options):
            return stack.enter_context(patch.object(obj, name, **options))
        replace(campaign, "BUNDLE", new=job)
        replace(campaign, "manifest", return_value=FILES)
        replace(campaign, "stage_all")
        replace(campaign, "stage")
        replace(campaign, "WRITER_SHA", new=campaign.hashlib.sha256(campaign.WRITER.read_bytes()).hexdigest())
        replace(campaign, "TVM_WRITER_SHA", new=campaign.hashlib.sha256(campaign.TVM_WRITER.read_bytes()).hexdigest())
        replace(campaign, "PLL1_WRITER_SHA", new=campaign.hashlib.sha256(campaign.PLL1_WRITER.read_bytes()).hexdigest())
        replace(campaign, "PLL4_WRITER_SHA", new=campaign.hashlib.sha256(campaign.PLL4_WRITER.read_bytes()).hexdigest())
        replace(campaign, "W22000_WRITER_SHA", new=campaign.hashlib.sha256(campaign.W22000_WRITER.read_bytes()).hexdigest())
        replace(campaign, "shell", side_effect=lambda command, timeout=8: b"W22000_WRITER_OK/ #" if "W22000_WRITER_OK" in command else b"PLL1_WRITER_OK/ #" if "PLL1_WRITER_OK" in command else b"PLL4_WRITER_OK/ #" if "PLL4_WRITER_OK" in command else b"TVM_WRITER_OK/ #" if "TVM_WRITER_OK" in command else b"WRITER_OK/ #" if "WRITER_OK" in command else b"gfx-request pid=1")
        replace(campaign, "boot_id", return_value=BOOT)
        replace(campaign, "preflight", return_value=BOOT)
        replace(campaign.bridge, "capture")
        connect = replace(campaign.socket, "create_connection", side_effect=sockets)
        try:
            campaign.run(path)
        except RuntimeError:
            assert scenario == "reordered" or scenario in FAULTS, "unexpected stop"
        else:
            assert scenario != "reordered" and scenario not in FAULTS, "unsafe scenario accepted"
    if fault:
        assert connect.call_count == FAULTS[scenario], (scenario, connect.call_count)
        assert not (path / "kpoll.log").exists() and not (path / "summary.txt").exists() and not (path / "core-id.log").exists()
        if scenario in ("pre-state", "vm-bit", "tvm-refused", "pll-unexpected", "pll1-refused", "pll1-bad-readback", "pll4-refused", "pll4-bad-readback", "w22-nonzero", "w22-refused", "w22-bad-readback"):
            assert not (path / "cycle.log").exists(), "GFX cycle must not start"
        return
    assert (path / "summary.txt").exists(), "summary must be on disk before the core read"
    summary = (path / "summary.txt").read_text()
    assert "order: MiscACG, voltage-manager check, SoC TVM, PLL1 +8, PLL4 +8" in summary and "pll1-write=" in summary and "pll4-write=" in summary and "w22000-write=" in summary and "+0x22000 bit 31" in summary and "status 0x2d100" in summary and "vm_sram 0x23004" in summary, summary
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
    for scenario in (None, "skipped", "reordered", *FAULTS):
        run(root, scenario)
print("PASS: Apple-order flow with the PLL1/PLL4 +8 replay and the +0x22000 store before the GFX cycle; every stop condition halts at the right step; core-ID gating unchanged")
