#!/usr/bin/env python3
"""Read-only PMGR region-0 word dump on a fresh J81 Linux observer boot (no GPU, no GFX power-on, no stores).

Stages the pinned pmgr-words-peek (the same read-only tool the campaigns use; it maps PMGR region 0
read-only, offsets below 0x40000, at most 64 per run, and waits for READ) and reads the requested
range in chunks of 64 words. Default range: PMGR +0x22000 .. +0x223fc (the per-domain 0x220xx words
of the A8 thread's list). One run per boot is enough; the output is plain text.
usage: j81_linux_pmgr_words.py <new logdir> [--first 0x22000] [--last 0x223fc]
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
BUNDLE = ROOT / "artifacts/live/private/j81-observer-paired-20261119-v1"
NOTES = "a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a"
PEEK_SHA = "b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502"
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
WORD = re.compile(rb"^w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})$")


def shell(command: str, timeout: float = 10) -> bytes:
    console = IPadShell()
    try:
        return console.run(command, timeout).encode()
    finally:
        console.close()


def clean(output: bytes) -> bytes:
    return output.replace(b"\r", b"").removesuffix(b"/ #").strip()


def chunk_read(offsets: list[int], path: Path) -> dict[int, int]:
    command = "/tmp/pmgr-words-peek " + " ".join(f"{o:x}" for o in offsets) + "\n"
    ready = f"stage=before-pmgr-words-read base=0x20e000000 words={len(offsets)}".encode()
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock, path.open("xb") as log:
        sock.settimeout(.5)
        sock.sendall(command.encode())
        data, acked, deadline = b"", False, time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            log.write(chunk); log.flush(); os.fsync(log.fileno()); data += chunk
            if len(data) > 65536:
                raise RuntimeError("peek output exceeded 64 KiB")
            lines = data.replace(b"\r\n", b"\n").split(b"\n")[:-1]
            if not acked and ready in lines:
                sock.sendall(b"READ\n"); acked = True; data = b""
                continue
            if acked and b"stage=after-pmgr-words-read" in lines:
                found = {}
                for line in lines:
                    if line.startswith(b"w "):
                        m = WORD.fullmatch(line)
                        if not m:
                            raise RuntimeError("malformed PMGR word")
                        found[int(m[1], 16)] = int(m[2], 16)
                if sorted(found) != sorted(offsets):
                    raise RuntimeError("incomplete PMGR chunk")
                return found
    raise RuntimeError("PMGR chunk incomplete")


def run(logdir: Path, first: int, last: int, bundle: Path = BUNDLE) -> None:
    if logdir.exists():
        raise FileExistsError(logdir)
    if first % 4 or last % 4 or not 0 <= first <= last < 0x40000:
        raise ValueError("offsets must be word aligned and below 0x40000")
    peek = bundle / "pmgr-words-peek"
    if hashlib.sha256(peek.read_bytes()).hexdigest() != PEEK_SHA:
        raise ValueError("pmgr-words-peek checksum mismatch")
    logdir.mkdir(mode=0o700, parents=True)
    pinned = clean(shell("cat /proc/sys/kernel/random/boot_id")).decode(errors="replace")
    if not BOOT.fullmatch(pinned):
        raise RuntimeError("missing boot ID")
    (logdir / "boot-id.txt").write_text(pinned + "\n")
    ok = clean(shell("test \"$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)\" = " + NOTES +
                     " && grep -q '^rootfs / rootfs ' /proc/mounts && printf WORDS_GO"))
    if not ok.endswith(b"WORDS_GO"):
        raise RuntimeError("preflight failed (wrong kernel or not the RAM root)")
    stage("172.16.42.1", "/tmp/pmgr-words-peek", peek.read_bytes())
    check = clean(shell("test \"$(sha256sum /tmp/pmgr-words-peek | cut -d ' ' -f1)\" = " + PEEK_SHA +
                        " && chmod +x /tmp/pmgr-words-peek && printf STAGED_OK"))
    if not check.endswith(b"STAGED_OK"):
        raise RuntimeError("tool not staged intact")
    values: dict[int, int] = {}
    offsets = list(range(first, last + 4, 4))
    for index in range(0, len(offsets), 64):
        values.update(chunk_read(offsets[index:index + 64], logdir / f"chunk-{index // 64:02d}.log"))
    if clean(shell("cat /proc/sys/kernel/random/boot_id")).decode(errors="replace") != pinned:
        raise RuntimeError("boot changed")
    (logdir / "words.txt").write_text("boot=" + pinned + "\n" + "".join(f"0x{o:06x} 0x{v:08x}\n" for o, v in sorted(values.items())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("logdir", type=Path)
    parser.add_argument("--first", type=lambda x: int(x, 16), default=0x22000)
    parser.add_argument("--last", type=lambda x: int(x, 16), default=0x223fc)
    args = parser.parse_args()
    try:
        run(args.logdir.resolve(), args.first, args.last)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"words read stopped: {error}; do not retry this boot\n")
