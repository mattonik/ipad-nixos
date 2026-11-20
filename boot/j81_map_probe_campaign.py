#!/usr/bin/env python3
"""Run the J81 mapping-only observation once on a fresh Linux observer boot.

Stages j81-map-walk.ko and j81-map-probe, loads the module, runs the probe (which maps three
physical pages through /dev/mem exactly like the core-ID reader and asks the module how each
virtual address is translated). No device register is read or written. One shot per boot.
"""
import argparse
import hashlib
import os
import re
import socket
import time
from pathlib import Path

from ipad_console import IPadShell
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "artifacts/live/private/j81-map-probe-experiment"
NOTES = "a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a"
MODULE_SHA = "e441f3543a39a0f625892058aa0b7734317db6a91528b11b3d611bb3968bc7f5"
PROBE_SHA = "484514320624c08324b12538a7228492763ec454c0f3319cb47c1632f34636b6"
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NAMES = ("page5", "gpc-state", "core")


def shell(command: str, timeout: float = 10) -> bytes:
    console = IPadShell()
    try:
        return console.run(command, timeout).encode()
    finally:
        console.close()


def clean(output: bytes) -> bytes:
    return output.replace(b"\r", b"").removesuffix(b"/ #").strip()


def boot_id() -> str:
    match = BOOT.fullmatch(clean(shell("cat /proc/sys/kernel/random/boot_id")).decode(errors="replace"))
    if not match:
        raise RuntimeError("missing boot ID")
    return match.group(0)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(data: bytes) -> dict:
    """Return {name: {key: value}} from the probe output; every named page must have a map and a walk line."""
    lines = data.replace(b"\r", b"").decode(errors="replace").splitlines()
    found: dict = {}
    for line in lines:
        if line.startswith("map name="):
            fields = dict(item.split("=", 1) for item in line.split()[1:] if "=" in item)
            found.setdefault(fields["name"], {}).update(fields)
        elif line.startswith("walk name="):
            fields = dict(item.split("=", 1) for item in line.split()[1:] if "=" in item)
            found.setdefault(fields["name"], {}).update(fields)
    if not all(n in found and "va" in found[n] and "result" in found[n] for n in NAMES):
        raise RuntimeError("incomplete probe output")
    if "stage=finished rc=0" not in lines:
        raise RuntimeError("probe did not finish cleanly")
    return found


def run(logdir: Path, directory: Path = DIR) -> None:
    if logdir.exists():
        raise FileExistsError(logdir)
    module, probe = directory / "j81-map-walk.ko", directory / "j81-map-probe"
    if digest(module) != MODULE_SHA or digest(probe) != PROBE_SHA:
        raise ValueError("artifact checksum mismatch")
    logdir.mkdir(mode=0o700, parents=True)
    pinned = boot_id()
    (logdir / "boot-id.txt").write_text(pinned + "\n")
    ok = clean(shell(
        "test \"$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)\" = " + NOTES +
        " && test ! -e /sys/devices/j81-map-walk && test ! -e /tmp/j81-map-probe.once && printf MAP_GO"))
    if not ok.endswith(b"MAP_GO"):
        raise RuntimeError("preflight failed (wrong kernel, module already loaded, or probe already run)")
    stage("172.16.42.1", "/tmp/j81-map-walk.ko", module.read_bytes())
    stage("172.16.42.1", "/tmp/j81-map-probe", probe.read_bytes())
    check = clean(shell(
        "test \"$(sha256sum /tmp/j81-map-walk.ko | cut -d ' ' -f1)\" = " + MODULE_SHA +
        " && test \"$(sha256sum /tmp/j81-map-probe | cut -d ' ' -f1)\" = " + PROBE_SHA +
        " && chmod +x /tmp/j81-map-probe && printf STAGED_OK"))
    if not check.endswith(b"STAGED_OK"):
        raise RuntimeError("files not staged intact")
    if boot_id() != pinned:
        raise RuntimeError("boot changed")
    load = clean(shell("insmod /tmp/j81-map-walk.ko && test -e /sys/devices/j81-map-walk/walk && printf MODULE_OK"))
    (logdir / "insmod.log").write_bytes(load + b"\n")
    if not load.endswith(b"MODULE_OK"):
        raise RuntimeError("module did not load")
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock, (logdir / "probe.log").open("xb") as log:
        sock.settimeout(.5)
        sock.sendall(b"mkdir /tmp/j81-map-probe.once && /tmp/j81-map-probe\n")
        data, deadline = b"", time.monotonic() + 30
        while time.monotonic() < deadline and b"stage=finished" not in data:
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); data += chunk
            if len(data) > 65536:
                raise RuntimeError("probe output exceeded 64 KiB")
    result = parse(data)
    if boot_id() != pinned:
        raise RuntimeError("boot changed")
    (logdir / "summary.txt").write_text("boot=" + pinned + "\n" + "\n".join(
        f"{n}: " + " ".join(f"{k}={v}" for k, v in result[n].items() if k != "name") for n in NAMES) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("logdir", type=Path)
    args = parser.parse_args()
    try:
        run(args.logdir.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"map probe stopped: {error}; do not retry this boot\n")
