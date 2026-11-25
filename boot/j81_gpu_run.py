#!/usr/bin/env python3
"""Run the j81-gpu bring-up (kernel/j81-gpu) once on a booted iPad, watchdog-supervised. TEST ONLY.

Stages the module, the wrapper (boot/j81-gpu-run) and the watchdog supervisor, then answers the supervisor handshake:
ARM once, READ before every step, FEED n after every completed step. If a step hangs the bus the host stops feeding and
the iPad's 20 s watchdog resets it; the log (every byte, fsynced) shows the last announced step.

usage: j81_gpu_run.py LOGDIR --module KO --supervisor BIN [--skip-pll1] [--peek 0xNNNN ...] [--stop-dashboard]
LOGDIR must not exist. One run per boot (the wrapper refuses a second one).
"""
import argparse
import hashlib
import os
import re
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage_gpu_test_bundle import stage  # noqa: E402
from ipad_console import IPadShell  # noqa: E402

HOST = "172.16.42.1"
BOOT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NOTES = "a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a"
STEPS = ("precheck", "pmgr", "activate", "batch")


def sh(cmd, timeout=10):
    c = IPadShell()
    try:
        return c.run(cmd, timeout)
    finally:
        c.close()


def run(logdir: Path, module: Path, supervisor: Path, skip_pll1: bool, peeks: list[str], stop_dashboard: bool, metas: list[str] = [], skip_pll4: bool = False, writes: list[str] = []) -> int:
    logdir.mkdir(parents=True)  # refuses an existing directory
    wrapper = Path(__file__).resolve().parent / "j81-gpu-run"
    files = {"j81-gpu.ko": module.read_bytes(), "j81-gpu-run": wrapper.read_bytes(),
             "gpu-watchdog-supervisor": supervisor.read_bytes()}
    shas = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    out = sh("cat /proc/sys/kernel/random/boot_id")
    m = BOOT.search(out)
    if not m:
        raise RuntimeError("no boot id")
    boot = m.group(0)
    notes = sh("sha256sum /sys/kernel/notes | cut -d ' ' -f1")
    if NOTES not in notes:
        raise RuntimeError("kernel notes mismatch: " + notes.strip())
    for name, data in files.items():
        stage(HOST, "/tmp/" + name, data)
    if skip_pll1:
        sh("touch /tmp/j81-gpu.skip-pll1")
    if skip_pll4:
        sh("touch /tmp/j81-gpu.skip-pll4")
    if peeks:
        sh("printf '%s\\n' " + " ".join(peeks) + " > /tmp/j81-gpu.peeks")
    if metas:
        sh("printf '%s\\n' " + " ".join(metas) + " > /tmp/j81-gpu.metas")
    if writes:
        sh("printf '%s\\n' " + " ".join(writes) + " > /tmp/j81-gpu.writes")
    if stop_dashboard:
        sh("pkill tablet-dashboard; killall tablet-dashboard 2>/dev/null; echo stopped")
    (logdir / "plan.txt").write_text(f"boot={boot}\nshas={shas}\nskip_pll1={skip_pll1}\nskip_pll4={skip_pll4}\npeeks={peeks}\nmetas={metas}\nwrites={writes}\n")
    cmd = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {shas["gpu-watchdog-supervisor"]} && '
           f'test "$(sha256sum /tmp/j81-gpu-run | cut -d " " -f 1)" = {shas["j81-gpu-run"]} && '
           f'/tmp/gpu-watchdog-supervisor --j81-gpu {shas["j81-gpu.ko"]} {boot}\n')
    fd = os.open(logdir / "console.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    result = []
    with os.fdopen(fd, "wb", buffering=0) as log, socket.create_connection((HOST, 23), timeout=5) as sock:
        sock.sendall(cmd.encode())
        buf = b""
        feeds = 0
        armed = False
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            sock.settimeout(1.0)
            try:
                chunk = sock.recv(4096)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            log.write(chunk)
            os.fsync(log.fileno())
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip(b"\r")
                if line in (b"ARM", b"READ") or re.fullmatch(rb"FEED [0-9]+", line):
                    continue  # echo of our own reply
                if not line.startswith(b"stage="):
                    continue
                if line == b"stage=before-watchdog-open":
                    sock.sendall(b"ARM\n")
                elif line.startswith(b"stage=watchdog-armed"):
                    armed = True
                elif line.startswith(b"stage=before-"):
                    if not armed:
                        raise RuntimeError("step before the watchdog armed")
                    sock.sendall(b"READ\n")
                elif line.startswith(b"stage=after-"):
                    feeds += 1
                    result.append(line.decode(errors="replace"))
                    sock.sendall(f"FEED {feeds}\n".encode())
                elif line.startswith(b"stage=failed-"):
                    result.append(line.decode(errors="replace"))
                elif line == b"stage=finished rc=0":
                    pass
                elif line.startswith(b"stage=finished"):
                    result.append(line.decode(errors="replace"))
                elif line == b"stage=watchdog-disarmed":
                    (logdir / "result.txt").write_text("\n".join(result) + "\n")
                    print("\n".join(result))
                    return 0
    (logdir / "result.txt").write_text("\n".join(result) + "\nINCOMPLETE: device state unknown, do not retry this boot\n")
    print("\n".join(result))
    print("INCOMPLETE: device state unknown, do not retry this boot")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("logdir", type=Path)
    p.add_argument("--module", type=Path, required=True)
    p.add_argument("--supervisor", type=Path, required=True)
    p.add_argument("--skip-pll1", action="store_true")
    p.add_argument("--skip-pll4", action="store_true")
    p.add_argument("--peek", action="append", default=[])
    p.add_argument("--meta", action="append", default=[])
    p.add_argument("--write", action="append", default=[], choices=["pa", "hn", "w1", "w2a", "h0", "h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "h9", "h10", "h11", "h7b", "h7c", "h7d", "h7e", "h7f", "h7g", "h7s", "h7m", "h7r", "h7z", "h3p", "h3pb", "h6x", "h6m", "h6md", "h7x", "h8n", "h12", "z0", "z1", "z2", "z3", "g0", "g1", "g2", "g3", "g4", "f1a", "f1", "f2"])
    p.add_argument("--stop-dashboard", action="store_true")
    a = p.parse_args()
    for off in a.peek:
        if not re.fullmatch(r"0x[0-9a-f]{4}", off):
            raise SystemExit("bad --peek offset " + off)
    for addr in a.meta:
        if not re.fullmatch(r"0x[0-9a-f]{8}", addr):
            raise SystemExit("bad --meta address " + addr)
    return run(a.logdir, a.module, a.supervisor, a.skip_pll1, a.peek, a.stop_dashboard, a.meta, a.skip_pll4, a.write)


if __name__ == "__main__":
    raise SystemExit(main())
