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


FAULTS = {"pre-state-pll": 1, "pre-state-mcc": 1, "pre-state-acg": 1, "vm-bit-at-start": 1,
          "pll1-refused": 2, "pll1-bad-readback": 3, "pll4-refused": 4, "pll4-bad-readback": 5,
          "mcc-refused": 6, "mcc-bad-readback": 7, "acg-refused": 8, "acg-bad-readback": 9,
          "tvm-refused": 10, "tvm-bad-readback": 11, "lost-after-cycle": 13, "lost-after-bridge": 15}
PRE_CYCLE = {"pre-state-pll", "pre-state-mcc", "pre-state-acg", "vm-bit-at-start", "pll1-refused", "pll1-bad-readback",
             "pll4-refused", "pll4-bad-readback", "mcc-refused", "mcc-bad-readback", "acg-refused", "acg-bad-readback",
             "tvm-refused", "tvm-bad-readback"}


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
    mwriter = Console({"acg-refused": ["stage=miscacg-skipped pre-value-not-zero"]}.get(scenario, BEFORE + AFTER))
    twriter = Console({"tvm-refused": ["stage=tvm-skipped pre-value-not-zero"]}.get(scenario, TBEFORE + TAFTER))
    p1w = Console({"pll1-refused": ["stage=pll1-skipped pre-value-not-expected"]}.get(scenario, P1B + P1A))
    p4w = Console({"pll4-refused": ["stage=pll4-skipped pre-value-not-expected"]}.get(scenario, P4B + P4A))
    mcc_before = ["stage=before-mcc-write base=0x20e022000 words=5", "old 0x022000 0x00000000", "old 0x022090 0x09070300",
                  "old 0x0220a0 0x09040300", "old 0x0220b0 0x09060300", "old 0x022130 0x09040300"]
    mcc_after = ["new 0x022000 0x80000000", "new 0x022090 0x89070300", "new 0x0220a0 0x89040300",
                 "new 0x0220b0 0x89060300", "new 0x022130 0x89040300", "stage=after-mcc-write"]
    mccw = Console({"mcc-refused": mcc_before[:1] + ["stage=mcc-skipped pre-value-not-expected"]}.get(scenario, mcc_before + mcc_after))
    base = dict(gfx=0x300)
    s0 = words(1 if scenario == "pre-state-acg" else 0, **base, v23000=0x100 if scenario == "vm-bit-at-start" else 1,
               w1=0x80480347 if scenario == "pre-state-pll" else 0x80480348,
               m90=0x89070300 if scenario == "pre-state-mcc" else 0x09070300)
    s1 = words(0, **base, w1=N1 if scenario != "pll1-bad-readback" else 0x80480348)
    s2 = words(0, **base, w1=N1, w4=N4 if scenario != "pll4-bad-readback" else 0x88480348)
    mcc_ok = scenario != "mcc-bad-readback"
    s3 = words(0, **base, w1=N1, w4=N4, w22=H if mcc_ok else 0, m90=0x89070300 if mcc_ok else 0x09070300,
               ma0=0x89040300 if mcc_ok else 0x09040300, mb0=0x89060300 if mcc_ok else 0x09060300,
               m130=0xc9040300 if mcc_ok else 0x09040300)  # bit 30 (status) appeared on this word, as on the device
    MCC = dict(w22=H, m90=0x89070300, ma0=0x89040300, mb0=0x89060300, m130=0x89040300)
    s4 = words(1 if scenario != "acg-bad-readback" else 0, **base, w1=N1, w4=N4, **MCC)
    s5 = words(1, **base, tvm=0 if scenario == "tvm-bad-readback" else 1, w1=N1, w4=N4, **MCC)
    a = words(1, tvm=0 if scenario == "lost-after-cycle" else 1, w1=N1, w4=N4, **MCC)
    b = words(1, tvm=1, w1=N1, w4=N4, **{**MCC, "m90": 0x09070300 if scenario == "lost-after-bridge" else 0x89070300})
    cfin = words(1, tvm=1, w1=N1, w4=N4, **MCC)
    sockets = [s0, p1w, s1, p4w, s2, mccw, s3, mwriter, s4, twriter, s5, cycle, a, Console([]), b, kpoll, cfin, core]
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
        replace(campaign, "MCC_WRITER_SHA", new=campaign.hashlib.sha256(campaign.MCC_WRITER.read_bytes()).hexdigest())
        replace(campaign, "shell", side_effect=lambda command, timeout=8: b"MCC_WRITER_OK/ #" if "MCC_WRITER_OK" in command else b"PLL1_WRITER_OK/ #" if "PLL1_WRITER_OK" in command else b"PLL4_WRITER_OK/ #" if "PLL4_WRITER_OK" in command else b"TVM_WRITER_OK/ #" if "TVM_WRITER_OK" in command else b"WRITER_OK/ #" if "WRITER_OK" in command else b"gfx-request pid=1")
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
        if scenario in PRE_CYCLE:
            assert not (path / "cycle.log").exists(), "GFX cycle must not start"
        return
    assert (path / "summary.txt").exists(), "summary must be on disk before the core read"
    summary = (path / "summary.txt").read_text()
    assert "order (Apple's): PLL1 +8, PLL4 +8" in summary and "pll1-write=" in summary and "pll4-write=" in summary and "mcc-write=" in summary and "MCC bank bit 31" in summary and "status 0x2d100" in summary and "vm_sram 0x23004" in summary, summary
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
print("PASS: Apple-order flow with PLL1/PLL4, the five MCC words, MiscACG and TVM in Apple's order before the GFX cycle; every stop condition halts at the right step; core-ID gating unchanged")
