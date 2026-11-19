#!/usr/bin/env python3
"""Run the observer-matched J81 PMGR/bridge/paired-GPC comparison once."""
import argparse
import hashlib
import os
import re
import socket
import time
from pathlib import Path

from ipad_console import IPadShell
import gpu_bridge_capture as bridge
import gpu_gpc_page5_kpoll_capture as kpoll
import gpu_pmgr_cycle_capture as cycle
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "artifacts/live/private/j81-observer-paired-20261119-v1"
NOTES = "a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a"
BOOT_ARTIFACTS = {
    "Pongo.bin": "1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575",
    "m1n1-linux.bin": "d8418f78cbe6b4cdf6096d40e2b8ea48d3cec21b667f6708a6e1c3da089ddec1",
}
OFFSETS = ("20320", "32000", "1008", "4008", "1c200", "2300c", "5004")
READY = b"stage=before-pmgr-words-read base=0x20e000000 words=7"
WORD = re.compile(rb"^w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})\r?$", re.M)
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict[str, str]:
    names = ("gpu-pmgr-cycle.ko", "gpu-pmgr-cycle-run", "gpu-pmgr-peek",
             "pmgr-words-peek", "gpu-bridge-once", "gfx-bridge-plan.bin",
             "gpu-watchdog-supervisor", "gpu-bridge-once-cycle-run",
             "j81-gpc-page5-kpoll.ko", "gpu-gpc-page5-kpoll-run-observer")
    receipt = {}
    for line in (BUNDLE / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if not match:
            raise ValueError("invalid SHA256SUMS entry")
        name = Path(match[2]).name
        if name in receipt and receipt[name] != match[1]:
            raise ValueError(f"ambiguous receipt: {name}")
        receipt[name] = match[1]
    pinned = dict(BOOT_ARTIFACTS)
    pinned.update({
        "j81-gpc-page5-kpoll.ko": "def7a657f995edf9b9d719ccc65cb9e15316a6394e463c02308c5b958dd82e59",
        "pmgr-words-peek": "b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502",
        "gfx-bridge-plan.bin": bridge.PLAN_SHA,
    })
    for name in (*names, *BOOT_ARTIFACTS):
        actual = digest(BUNDLE / name)
        if receipt.get(name) != actual or pinned.get(name, actual) != actual:
            raise ValueError(f"artifact checksum mismatch: {name}")
    return {name: receipt[name] for name in names}


def shell(command: str, timeout: float = 8) -> bytes:
    console = IPadShell()
    try:
        return console.run(command, timeout).encode()
    finally:
        console.close()


def boot_id() -> str:
    match = BOOT.fullmatch(shell("cat /proc/sys/kernel/random/boot_id").decode(errors="replace"))
    if not match:
        raise RuntimeError("missing boot ID")
    return match.group(0)


def preflight() -> str:
    output = shell(
        "test \"$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)\" = " + NOTES +
        " && test ! -e /sys/module/gpu_pmgr_cycle && test ! -e /sys/module/gpc_page5_kpoll && "
        "test ! -e /tmp/gpu-bridge-once.once && test ! -e /tmp/gpu-gpc-init.once && "
        "test ! -e /tmp/gpu-gpc-page5-kpoll.once && grep -q '^rootfs / rootfs ' /proc/mounts && "
        "! grep -q '^/dev/' /proc/mounts && printf OBSERVER_GO"
    )
    if output != b"OBSERVER_GO":
        raise RuntimeError("observer preflight failed")
    return boot_id()


def stage_all(files: dict[str, str]) -> None:
    remote = {
        "gpu-pmgr-cycle.ko": "/tmp/gpu-pmgr-cycle.ko",
        "gpu-pmgr-cycle-run": "/tmp/gpu-pmgr-cycle-run",
        "gpu-pmgr-peek": "/tmp/gpu-pmgr-peek",
        "pmgr-words-peek": "/tmp/pmgr-words-peek",
        "gpu-bridge-once": "/tmp/gpu-bridge-once",
        "gfx-bridge-plan.bin": "/tmp/gfx-bridge-plan.bin",
        "gpu-watchdog-supervisor": "/tmp/gpu-watchdog-supervisor",
        "gpu-bridge-once-cycle-run": "/tmp/gpu-bridge-once-cycle-run",
        "j81-gpc-page5-kpoll.ko": "/tmp/j81-gpc-page5-kpoll.ko",
        "gpu-gpc-page5-kpoll-run-observer": "/tmp/gpu-gpc-page5-kpoll-run",
    }
    for name, destination in remote.items():
        data = (BUNDLE / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != files[name]:
            raise ValueError(f"artifact changed: {name}")
        stage("172.16.42.1", destination, data)


def parse_words(data: bytes) -> dict[str, int]:
    found = []
    for line in data.splitlines():
        if line.startswith(b"w "):
            match = WORD.fullmatch(line)
            if not match:
                raise RuntimeError("malformed PMGR word")
            found.append((match[1].decode(), int(match[2], 16)))
    expected = tuple(f"{int(offset, 16):06x}" for offset in OFFSETS)
    if tuple(offset for offset, _ in found) != expected or b"stage=after-pmgr-words-read" not in data.splitlines():
        raise RuntimeError("incomplete PMGR snapshot")
    return dict(found)


def snapshot(path: Path) -> dict[str, int]:
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        sock.settimeout(.5)
        sock.sendall(("/tmp/pmgr-words-peek " + " ".join(OFFSETS) + "\n").encode())
        data, acked, deadline = b"", False, time.monotonic() + 30
        with path.open("xb") as log:
            while time.monotonic() < deadline:
                try:
                    chunk = sock.recv(4096)
                except TimeoutError:
                    continue
                if not chunk:
                    break
                log.write(chunk); log.flush(); os.fsync(log.fileno()); data += chunk
                if len(data) > 65536:
                    raise RuntimeError("PMGR snapshot exceeded 64 KiB")
                complete = data.replace(b"\r\n", b"\n").split(b"\n")[:-1]
                if not acked and READY in complete:
                    sock.sendall(b"READ\n")
                    acked = True
                    data = b""
                    continue
                if acked and b"stage=after-pmgr-words-read" in complete:
                    return parse_words(data)
    raise RuntimeError("PMGR snapshot incomplete")


def run(logdir: Path) -> None:
    if logdir.exists():
        raise FileExistsError(logdir)
    files = manifest()
    logdir.mkdir(mode=0o700, parents=True)
    before = boot_id()
    pinned = preflight()
    if before != pinned:
        raise RuntimeError("boot changed during preflight")
    (logdir / "manifest.txt").write_text("\n".join(f"{v}  {k}" for k, v in sorted(files.items())) + "\n")
    (logdir / "boot-id.txt").write_text(pinned + "\n")

    def same_boot():
        if boot_id() != pinned:
            raise RuntimeError("boot changed during campaign")

    stage_all(files)
    same_boot()
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        cycle.capture(sock, logdir / "cycle.log", files["gpu-pmgr-cycle.ko"], NOTES, 40)
    same_boot()
    observer_rows = shell("dmesg | grep -F 'gfx-request pid='")
    (logdir / "gfx-request.log").write_bytes(observer_rows + b"\n")
    a = snapshot(logdir / "snapshot-a.log")
    same_boot()
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        bridge.capture(sock, logdir / "bridge.log", files["gpu-bridge-once"],
                       (BUNDLE / "gfx-bridge-plan.bin").read_bytes(), 90, supervised=True,
                       supervisor_hash=files["gpu-watchdog-supervisor"], cycle_payload=True,
                       cycle_wrapper_hash=files["gpu-bridge-once-cycle-run"])
    same_boot()
    b = snapshot(logdir / "snapshot-b.log")
    same_boot()
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        result = kpoll.capture(sock, logdir / "kpoll.log", files["j81-gpc-page5-kpoll.ko"],
                               files["gpu-watchdog-supervisor"], files["gpu-gpc-page5-kpoll-run-observer"],
                               pinned, "paired")
    same_boot()
    c = snapshot(logdir / "snapshot-c.log")
    if boot_id() != pinned:
        raise RuntimeError("boot changed during campaign")
    (logdir / "summary.txt").write_text(
        "boot=" + pinned + "\n" +
        "A=" + repr(a) + "\nB=" + repr(b) + "\nC=" + repr(c) + "\n" +
        f"pre-gpc MiscACG=0x{b['032000']:08x} bit0={b['032000'] & 1}\n" +
        "\n".join(kpoll.describe(result)) + "\n" +
        "page5-first=0x%08x page5-later=0x%08x\n" % (result["first"], result["later"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("logdir", type=Path, nargs="?")
    parser.add_argument("--bundle", type=Path, default=BUNDLE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        BUNDLE = args.bundle.resolve()
        if args.verify_only:
            manifest()
            print("Verified observer artifacts and receipt")
        elif args.logdir is None:
            parser.error("provide a new log directory or --verify-only")
        else:
            run(args.logdir.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"campaign stopped: {error}; do not retry this boot\n")
