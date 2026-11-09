#!/usr/bin/env python3
"""Capture GFX perf words on either side of one guarded power-up.

Two read-only snapshots in one boot are intentional. The target has no
watchdog; a host timeout cannot recover a stuck MMIO transaction. Stop on
any failure, never retry this sequence in the same boot.
"""
import hashlib
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import gpu_pmgr_perf_capture as perf
import gpu_power_capture as power
from ipad_telnet_run import run
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
HOST = '172.16.42.1'
NOTES = '82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014'
FILES = {
    '/tmp/gpu-pmgr-perf-peek': ('artifacts/live/gpu-pmgr-perf-v2/gpu-pmgr-perf-peek', 'd2ef11e1517d9cd70f8cdf174878604c7a10d9efb3116521b1cfbd132e187f84'),
    '/tmp/gpu-pmgr-once.ko': ('artifacts/live/private/gpu-test-staging/gpu-pmgr-once.ko', '39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89'),
    '/tmp/gpu-pmgr-peek': ('artifacts/live/private/gpu-test-staging/gpu-pmgr-peek', '78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd'),
    '/tmp/gpu-pmgr-once-run': ('artifacts/live/private/gpu-test-staging/gpu-pmgr-once-run', '4fb50cd7bfdebc28ed5ae5c64815e979deec08171a95e9ff2f928322814bf181'),
}
# The tested archived binary uses +4/w300 labels, unlike the current source.
perf.LINE = re.compile(rb'(ps|ctl|w300|perf\d\d(?:\+4)?) raw=0x([0-9a-f]{8})')
perf.EXPECTED = {'ps', 'ctl', 'w300'} | {f'perf{n:02d}{s}' for n in range(16) for s in ('', '+4')}


def boot_id():
    out, code = run('cat /proc/sys/kernel/random/boot_id', timeout=10)
    if code or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', out):
        raise RuntimeError('cannot verify boot ID')
    return out


def same_boot(expected):
    if boot_id() != expected:
        raise RuntimeError('boot ID changed; stop')


def read_snapshot(path, expected_ps):
    with socket.create_connection((HOST, 23), timeout=5) as sock:
        time.sleep(.25)
        data = perf.capture(sock, path, 30)
    values = {name.decode(): int(value, 16) for name, value in perf.LINE.findall(data)}
    if values['ps'] != expected_ps:
        raise RuntimeError(f'unexpected PMGR state {values["ps"]:#x}; stop')
    return values


def execute(directory):
    subprocess.run(['bash', str(ROOT / 'boot/j81_preflight.sh'), 'gpu-pmgr-once'], check=True, timeout=20)
    subprocess.run(['bash', str(ROOT / 'boot/j81_preflight.sh'), 'perf-peek'], check=True, timeout=20)
    original_boot = boot_id()
    payloads = {}
    for remote, (relative, expected) in FILES.items():
        data = (ROOT / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f'hash mismatch: {relative}')
        payloads[remote] = data
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    (directory / 'boot-id.txt').write_text(original_boot + '\n')
    for remote, data in payloads.items():
        stage(HOST, remote, data)
    same_boot(original_boot)
    before = read_snapshot(directory / 'before.log', 0x300)
    same_boot(original_boot)
    with socket.create_connection((HOST, 23), timeout=5) as sock:
        time.sleep(.25)
        power.capture(sock, directory / 'power.log', FILES['/tmp/gpu-pmgr-once.ko'][1], NOTES, 30)
    same_boot(original_boot)
    after = read_snapshot(directory / 'after.log', 0x3ff)
    same_boot(original_boot)
    for name in sorted(before):
        print(f'{name}: {before[name]:08x} -> {after[name]:08x}' + (' CHANGED' if before[name] != after[name] else ''))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: gpu_pmgr_perf_pair.py NEW_PRIVATE_LOG_DIRECTORY')
    try:
        execute(Path(sys.argv[1]))
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, SystemExit) as error:
        raise SystemExit(f'PAIR STOPPED: {error}; do not retry in this boot')
