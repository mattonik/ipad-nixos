#!/usr/bin/env python3
"""Run the observer-matched J81 PMGR/bridge/paired-GPC comparison once."""
import argparse
import hashlib
import os
import re
import socket
import time
from pathlib import Path

import gpu_bridge_capture as bridge
import gpu_gpc_page5_kpoll_capture as kpoll
import gpu_pmgr_cycle_capture as cycle
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "artifacts/live/private/j81-observer-paired-20261119-v1"
NOTES = "a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a"
OFFSETS = ("20320", "32000", "1008", "4008", "1c200", "2300c", "5004")
READY = b"stage=before-pmgr-words-read base=0x20e000000 words=7"
WORD = re.compile(rb"w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})")
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict[str, str]:
    names = ("gpu-pmgr-cycle.ko", "gpu-pmgr-cycle-run", "gpu-pmgr-peek",
             "pmgr-words-peek", "gpu-bridge-once", "gfx-bridge-plan.bin",
             "gpu-watchdog-supervisor", "gpu-bridge-once-cycle-run",
             "j81-gpc-page5-kpoll.ko", "gpu-gpc-page5-kpoll-run-observer")
    values = {name: digest(BUNDLE / name) for name in names}
    if digest(BUNDLE / "Pongo.bin") == "" or digest(BUNDLE / "m1n1-linux.bin") == "":
        raise ValueError("empty boot artifact digest")
    return values


def shell(command: str, timeout: float = 8) -> bytes:
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        sock.settimeout(.25)
        time.sleep(.2)
        try:
            while sock.recv(8192):
                pass
        except TimeoutError:
            pass
        token = "__J81_DONE__"
        sock.sendall((command + "; printf '" + token + "\\n'\n").encode())
        output, deadline = b"", time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(8192)
            except TimeoutError:
                continue
            if not chunk:
                break
            output += chunk
            if token.encode() in output:
                return output
    raise RuntimeError("shell command did not complete")


def boot_id() -> str:
    match = BOOT.search(shell("cat /proc/sys/kernel/random/boot_id").decode(errors="replace"))
    if not match:
        raise RuntimeError("missing boot ID")
    return match.group(0)


def preflight(files: dict[str, str]) -> str:
    output = shell(
        "test \"$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)\" = " + NOTES +
        " && test ! -e /sys/module/gpu_pmgr_cycle && test ! -e /sys/module/gpc_page5_kpoll && "
        "test ! -e /tmp/gpu-gpc-page5-kpoll.once && grep -q '^rootfs / rootfs ' /proc/mounts && "
        "! grep -q '^/dev/' /proc/mounts && printf OBSERVER_GO"
    )
    if b"OBSERVER_GO" not in output:
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
        if digest(BUNDLE / name) != files[name]:
            raise ValueError(f"artifact changed: {name}")
        stage("172.16.42.1", destination, (BUNDLE / name).read_bytes())


def parse_words(data: bytes) -> dict[str, int]:
    found = [(offset.decode(), int(value, 16)) for offset, value in WORD.findall(data)]
    expected = tuple(f"{int(offset, 16):06x}" for offset in OFFSETS)
    if tuple(offset for offset, _ in found) != expected or b"stage=after-pmgr-words-read" not in data:
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
                if not acked and READY in data:
                    sock.sendall(b"READ\n"); acked = True; data = b""
                if acked and b"stage=after-pmgr-words-read" in data:
                    return parse_words(data)
    raise RuntimeError("PMGR snapshot incomplete")


def run(logdir: Path) -> None:
    if logdir.exists():
        raise FileExistsError(logdir)
    files = manifest()
    logdir.mkdir(parents=True)
    before = boot_id()
    pinned = preflight(files)
    if before != pinned:
        raise RuntimeError("boot changed during preflight")
    (logdir / "manifest.txt").write_text("\n".join(f"{v}  {k}" for k, v in sorted(files.items())) + "\n")
    stage_all(files)
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        cycle.capture(sock, logdir / "cycle.log", files["gpu-pmgr-cycle.ko"], NOTES, 40)
    a = snapshot(logdir / "snapshot-a.log")
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        bridge.capture(sock, logdir / "bridge.log", files["gpu-bridge-once"],
                       (BUNDLE / "gfx-bridge-plan.bin").read_bytes(), 90, supervised=True,
                       supervisor_hash=files["gpu-watchdog-supervisor"], cycle_payload=True,
                       cycle_wrapper_hash=files["gpu-bridge-once-cycle-run"])
    b = snapshot(logdir / "snapshot-b.log")
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        result = kpoll.capture(sock, logdir / "kpoll.log", files["j81-gpc-page5-kpoll.ko"],
                               files["gpu-watchdog-supervisor"], files["gpu-gpc-page5-kpoll-run-observer"],
                               pinned, "paired")
    c = snapshot(logdir / "snapshot-c.log")
    if boot_id() != pinned:
        raise RuntimeError("boot changed during campaign")
    (logdir / "summary.txt").write_text(
        "boot=" + pinned + "\n" +
        "A=" + repr(a) + "\nB=" + repr(b) + "\nC=" + repr(c) + "\n" +
        "page5-first=0x%08x page5-later=0x%08x\n" % (result["first"], result["later"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("logdir", type=Path)
    args = parser.parse_args()
    try:
        run(args.logdir.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"campaign stopped: {error}; do not retry this boot\n")
