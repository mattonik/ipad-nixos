"""Run the campaign against scripted console replies. No device connection is opened."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_observer_paired_campaign as campaign

BOOT = "12345678-1234-1234-1234-123456789abc"
SHA = "a" * 64
PAIRED = (
    "result=ok mode=paired raw=0x00000001 polls=11 prewrite_ns=12000 postwrite_ns=11000 "
    "first_valid=1 first=0x00000000 first_ns=650 "
    "later_valid=1 later=0x40000000 later_ns=101000"
)
FILES = dict.fromkeys((
    "gpu-pmgr-cycle.ko", "gpu-pmgr-cycle-run", "gpu-pmgr-peek", "pmgr-words-peek",
    "gpu-bridge-once", "gfx-bridge-plan.bin", "gpu-watchdog-supervisor",
    "gpu-bridge-once-cycle-run", "j81-gpc-page5-kpoll.ko", "gpu-gpc-page5-kpoll-run-observer",
), SHA)


class Console:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def settimeout(self, _):
        pass

    def sendall(self, data):
        self.commands.append(data)

    def recv(self, _):
        line = next(self.lines, None)
        return b"" if line is None else (line + "\r\n").encode()


def words(acg, incomplete=False):
    values = (0x3ff, acg, 0x80480348, 0x88480348, 0x80000000, 0, 0)
    rows = [f"w 0x{int(offset, 16):06x} raw=0x{value:08x}"
            for offset, value in zip(campaign.OFFSETS, values)]
    if incomplete:
        del rows[1]
    return Console([campaign.READY.decode(), *rows, "stage=after-pmgr-words-read"])


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
        "stage=before-gpc-state address=0x201e01000 width=32",
        "stage=after-gpc-state raw=0x00000000",
        "stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=paired",
        "checkpoint=before-kernel-batch",
        "checkpoint=kernel-batch " + PAIRED, "stage=after-gpc-page5-kpoll " + PAIRED,
        "stage=finished rc=0", *([] if fault == "lost-disarm" else ["stage=watchdog-disarmed"]),
    ])
    reads = [words(0), words(1, incomplete=fault == "missing-b"), words(0)]
    sockets = [cycle, reads[0], Console([]), reads[1], kpoll, reads[2]]
    with ExitStack() as stack:
        def replace(obj, name, **options):
            return stack.enter_context(patch.object(obj, name, **options))

        replace(campaign, "BUNDLE", new=job)
        replace(campaign, "manifest", return_value=FILES)
        replace(campaign, "stage_all")
        replace(campaign, "shell", return_value=b"gfx-request pid=1")
        replace(campaign, "boot_id", return_value=BOOT)
        replace(campaign, "preflight", return_value=BOOT)
        bridge = replace(campaign.bridge, "capture")
        connect = replace(campaign.socket, "create_connection", side_effect=sockets)
        try:
            campaign.run(path)
        except RuntimeError:
            if fault is None:
                raise
        else:
            assert fault is None, f"{fault} accepted"

    assert bridge.call_count == 1 and cycle.commands[-1] == b"CYCLE\n"
    assert (path / "boot-id.txt").read_text().strip() == BOOT
    assert (path / "snapshot-b.log").exists()
    if fault:
        assert not (path / "snapshot-c.log").exists()
        assert not (path / "summary.txt").exists()
        assert connect.call_count == (4 if fault == "missing-b" else 5)
        return
    assert connect.call_count == 6
    assert all(b"READ\n" in sock.commands for sock in reads)
    assert kpoll.commands[-1] == b"FEED 3\n"
    assert b" paired\n" in kpoll.commands[0] and BOOT.encode() in kpoll.commands[0]
    assert PAIRED in (path / "kpoll.log").read_text()
    summary = (path / "summary.txt").read_text()
    assert BOOT in summary and "0x40000000" in summary
    assert "pre-gpc MiscACG=0x00000001 bit0=1" in summary


with TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "gfx-bridge-plan.bin").write_bytes(b"fixture for mocked bridge only")
    for scenario in (None, "missing-b", "lost-disarm"):
        run(root, scenario)
print("PASS: same-boot snapshots and real paired parser; incomplete B or lost disarm stops the campaign")
