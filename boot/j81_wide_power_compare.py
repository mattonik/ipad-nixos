#!/usr/bin/env python3
"""Fresh J81 boot: restore 20 observed domains, then perform the DWI/GPC comparison."""
import argparse
import os
import re
import socket
import subprocess
import time
from pathlib import Path

import gpu_campaign as base
import j81_dwi_gpu_compare as dwi
from stage_gpu_test_bundle import stage

NAME = 'pmgr-ps-restore'
HASH = '90474674554b3e3abac9f15e3d5d189b43a8a816feddf97dacdb8a32286f1d18'
DOMAINS = (
    ('dwi', 0x120), ('i2c1', 0x168), ('i2c2', 0x170), ('i2c3', 0x178),
    ('uart1', 0x1a8), ('uart2', 0x1b0), ('uart4', 0x1c0), ('uart6', 0x1d0),
    ('uart7', 0x1d8), ('uart8', 0x1e0), ('ispsens0', 0x210), ('ispsens1', 0x218),
    ('usb2host0', 0x258), ('usb2host1', 0x268), ('usb2host2', 0x278),
    ('disp1_busmux', 0x2c0), ('isp', 0x2d0), ('media', 0x2d8), ('venc', 0x300),
    ('pcie_aux', 0x310),
)
PARENTS = ('201f8', '20248', '20250')  # SIO_P, USB, USBCTRL; from captured ADT
BAD_FLAGS = (1 << 31) | (1 << 11) | (1 << 10)


def parent_check(boot_id, directory):
    result = dwi.remote("printf 'READ\\n' | /tmp/pmgr-words-peek " + ' '.join(PARENTS),
                        boot_id, directory / 'external-parent-ps.log')
    matches = re.findall(r'^w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})$', result, re.MULTILINE)
    values = {f'{int(k,16):x}': int(v,16) for k, v in matches}
    if len(matches) != len(PARENTS) or set(values) != set(PARENTS) or \
       'stage=after-pmgr-words-read' not in result.splitlines() or \
       any((v & 0xf0) != 0xf0 or v & BAD_FLAGS for v in values.values()):
        raise ValueError('external parent PS missing, inactive, reset or disabled')


def domain_snapshot(boot_id, log, require_on):
    offsets = [0x20000 + offset for _, offset in DOMAINS]
    output = dwi.remote("printf 'READ\\n' | /tmp/pmgr-words-peek " +
                        ' '.join(f'{x:x}' for x in offsets), boot_id, log)
    rows = re.findall(r'^w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})$', output, re.MULTILINE)
    values = {int(k,16): int(v,16) for k,v in rows}
    if len(rows) != len(offsets) or set(values) != set(offsets) or \
       'stage=after-pmgr-words-read' not in output.splitlines():
        raise ValueError('incomplete domain state snapshot')
    if require_on and any((v & 0xff) != 0xff or v & BAD_FLAGS for v in values.values()):
        raise ValueError('a restored domain is not active before GPC')
    return values


def restore_capture(sock, boot_id, log, timeout=180):
    command = f"{dwi.guard(boot_id)} && /tmp/{NAME} " + ' '.join(n for n, _ in DOMAINS)
    command += ' || echo stage=guard-or-tool-failed\n'
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb', buffering=0) as out:
        sock.sendall(command.encode())
        buf = b''; phase = 'start'; baseline = []; index = 0; deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            out.write(chunk); os.fsync(out.fileno()); buf += chunk
            if len(buf) > 65536: raise RuntimeError('restore capture exceeded 64 KiB')
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1); line = line.strip(b'\r')
                if phase == 'start' and line == b'stage=before-ps-read count=20':
                    sock.sendall(b'READ\n'); phase = 'baseline'; continue
                if phase == 'baseline':
                    m = re.fullmatch(rb'stage=ps-read name=([a-z0-9_]+) address=0x([0-9a-f]+) raw=0x([0-9a-f]{8})', line)
                    if m:
                        if len(baseline) >= len(DOMAINS): raise RuntimeError('too many baseline entries')
                        name, offset = DOMAINS[len(baseline)]
                        raw = int(m[3], 16)
                        if m[1].decode() != name or int(m[2],16) != 0x20e020000 + offset or raw & BAD_FLAGS:
                            raise RuntimeError('unexpected or unsafe domain baseline')
                        baseline.append(raw)
                        if len(baseline) == len(DOMAINS): phase = 'domain'
                        continue
                if phase == 'domain' and index < len(DOMAINS):
                    name, offset = DOMAINS[index]
                    before = re.fullmatch(rb'stage=before-ps-write name=([a-z0-9_]+) address=0x([0-9a-f]+) raw=0x([0-9a-f]{8}) set=0xf', line)
                    already = re.fullmatch(rb'result=already-on name=([a-z0-9_]+) raw=0x([0-9a-f]{8})', line)
                    if before:
                        raw = int(before[3],16)
                        if before[1].decode() != name or int(before[2],16) != 0x20e020000+offset or raw & BAD_FLAGS or (raw & 0xff) != 0:
                            raise RuntimeError('unexpected domain pre-write state')
                        sock.sendall(b'WRITE\n'); phase = 'written'; continue
                    if already:
                        raw = int(already[2],16)
                        if already[1].decode() != name or raw & BAD_FLAGS or raw & 0xff != 0xff:
                            raise RuntimeError('unexpected already-on state')
                        index += 1; continue
                if phase == 'written':
                    m = re.fullmatch(rb'result=on name=([a-z0-9_]+) raw=0x([0-9a-f]{8}) polls=([0-9]+)', line)
                    if m:
                        raw = int(m[2],16)
                        if m[1].decode() != DOMAINS[index][0] or raw & BAD_FLAGS or raw & 0xff != 0xff or int(m[3]) >= 100:
                            raise RuntimeError('invalid domain post-write state')
                        index += 1; phase = 'domain'; continue
                if phase == 'domain' and index == len(DOMAINS) and line == b'result=all-on':
                    return
                if line.startswith((b'stage=', b'result=')):
                    raise RuntimeError('unexpected restore checkpoint')
    raise RuntimeError('restore capture incomplete; device state unknown')


def run(directory):
    dwi.FILES[NAME] = ('j81-pmgr-ps-restore-bundle-v1', HASH)
    dwi.verify()
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    check = subprocess.run(['bash', 'boot/j81_preflight.sh', 'gpc-page5-kpoll'], cwd=dwi.ROOT,
                           capture_output=True, text=True, timeout=30)
    (directory / 'device-preflight.log').write_text(check.stdout + check.stderr)
    if check.returncode or 'GO: gpc-page5-kpoll' not in check.stdout.splitlines():
        raise ValueError('fresh preflight failed')
    preflight = base.preflight()
    (directory / 'preflight.log').write_text(preflight)
    boot_id = base.parse_preflight(preflight)
    print(f'boot={boot_id}', flush=True)
    for name, (folder, digest) in dwi.FILES.items():
        import hashlib
        data = (dwi.BUNDLES / folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError(f'changed binary: {name}')
        stage('172.16.42.1', '/tmp/' + name, data)
    before = dwi.snapshot(boot_id, directory, 'before-restore')
    print(f"baseline DWI=0x{before['20120']:08x}", flush=True)
    parent_check(boot_id, directory)
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        restore_capture(sock, boot_id, directory / 'restore.log')
    ready = dwi.snapshot(boot_id, directory, 'before-gpc')
    if ready['20120'] & 0xff != 0xff: raise ValueError('DWI not active')
    def before_kpoll(current_boot):
        if current_boot != boot_id: raise ValueError('boot ID changed')
        parent_check(boot_id, directory / 'gpc-campaign')
        domain_snapshot(boot_id, directory / 'before-request-domains.log', True)
    print('restored domains; starting guarded GPC comparison', flush=True)
    dwi.kpoll.run(directory / 'gpc-campaign', 'paired', expected_boot_id=boot_id, before_kpoll=before_kpoll)
    domain_snapshot(boot_id, directory / 'after-gpc-domains.log', False)
    dwi.snapshot(boot_id, directory, 'after-gpc')
    time.sleep(10)
    domain_snapshot(boot_id, directory / 'after-10s-domains.log', False)
    dwi.snapshot(boot_id, directory, 'after-10s')
    print(f'capture={directory}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logdir', type=Path)
    args = parser.parse_args()
    try: run(args.logdir.resolve())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as e:
        parser.exit(1, f'campaign stopped: {e}; device state may have changed; do not retry on this boot\n')


if __name__ == '__main__': main()
