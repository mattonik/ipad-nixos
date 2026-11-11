#!/usr/bin/env python3
"""One fresh J81 boot: DWI on, then compare candidate PMU rows around GPC state 1."""
import argparse
import hashlib
import os
import re
import socket
import time
from pathlib import Path

import gpu_campaign as base
import ipad_telnet_run
import j81_gpc_page5_kpoll_campaign as kpoll
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BUNDLES = ROOT / 'artifacts/live/private'
FILES = {
    'pmgr-words-peek': ('j81-pmgr-words-bundle-v1', 'b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502'),
    'i2ctransfer': ('j81-pmgr-words-bundle-v1', '4d030c81fdc8af5b998c31062dfe8eb1c7cd3280cd6aa61020d4e20f3326ac70'),
    'pmgr-dwi-on': ('j81-pmgr-dwi-on-bundle-v1', '0fa252375e7fb1d97b64adf55e4cb0b4f7420906ac942163a78728456ab65258'),
}
OFFSETS = ('20120', '23004', '23008', '2300c', '23010', '5000', '5004', '5008', '5018', '1c200')
ROWS = ('00', '28', '50', 'c8')
BOOT = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')


def verify():
    kpoll.verify()
    for name, (directory, digest) in FILES.items():
        data = (BUNDLES / directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'checksum mismatch: {name}')


def guard(boot_id):
    if not BOOT.fullmatch(boot_id):
        raise ValueError('invalid boot ID')
    guard = f'test "$(cat /proc/sys/kernel/random/boot_id)" = {boot_id}'
    for name, (_, digest) in FILES.items():
        guard += f' && test "$(sha256sum /tmp/{name} | cut -d " " -f1)" = {digest}'
    return guard


def remote(command, boot_id, log):
    output, rc = ipad_telnet_run.run(f'{guard(boot_id)} && {{ {command}; }}', timeout=45)
    with log.open('x') as f:
        os.chmod(log, 0o600)
        f.write(output + '\n'); f.flush(); os.fsync(f.fileno())
    if rc:
        raise RuntimeError(f'{log.name}: command failed ({rc}); stop for this boot')
    return output.replace('\r', '')



def dwi_capture(sock, boot_id, log, timeout=30):
    command = f'{guard(boot_id)} && /tmp/pmgr-dwi-on || echo stage=guard-or-tool-failed\n'
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb', buffering=0) as out:
        sock.sendall(command.encode())
        buf = b''; phase = 0; deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            out.write(chunk); os.fsync(out.fileno()); buf += chunk
            if len(buf) > 65536:
                raise RuntimeError('DWI capture exceeded 64 KiB')
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1); line = line.strip(b'\r')
                if phase == 0 and line == b'stage=before-dwi-read address=0x20e020120 width=32':
                    sock.sendall(b'READ\n'); phase = 1
                elif phase == 1 and re.fullmatch(rb'stage=after-dwi-read raw=0x[0-9a-f]{8} target=[0-9]+ actual=[0-9]+', line):
                    phase = 2
                elif phase == 2 and line == b'stage=before-dwi-write address=0x20e020120 set=0xf':
                    sock.sendall(b'WRITE\n'); phase = 3
                elif phase == 3 and re.fullmatch(rb'stage=after-dwi-write raw=0x[0-9a-f]{8} target=15 actual=15', line):
                    phase = 4
                elif phase == 2 and line == b'result=already-on':
                    return
                elif phase == 4 and re.fullmatch(rb'result=on polls=[0-9]+', line):
                    return
                elif line.startswith((b'stage=', b'result=')):
                    raise RuntimeError('unexpected DWI checkpoint')
    raise RuntimeError('DWI capture incomplete; device state unknown')

def parse_words(output):
    values = {}
    for line in output.splitlines():
        m = re.fullmatch(r'w 0x([0-9a-f]{6}) raw=0x([0-9a-f]{8})', line.strip())
        if m:
            key = f'{int(m[1], 16):x}'
            if key in values:
                raise ValueError('duplicate PMGR word')
            values[key] = int(m[2], 16)
    if set(values) != set(OFFSETS) or 'stage=after-pmgr-words-read' not in output.splitlines():
        raise ValueError('incomplete PMGR sample')
    return values


def snapshot(boot_id, directory, label):
    command = "printf 'READ\\n' | /tmp/pmgr-words-peek " + ' '.join(OFFSETS)
    words = parse_words(remote(command, boot_id, directory / f'{label}-pmgr.log'))
    for low in ROWS:
        output = remote(f'/tmp/i2ctransfer -f -y 0 w2@0x3c 0x01 0x{low} r8', boot_id,
                        directory / f'{label}-pmu-01{low}.log')
        if not re.fullmatch(r'(?:0x[0-9a-fA-F]{2}\s+){7}0x[0-9a-fA-F]{2}\s*', output.strip()):
            raise ValueError(f'invalid PMU row 0x01{low}')
    return words


def run(directory):
    verify()
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    output = base.preflight()
    (directory / 'preflight.log').write_text(output)
    boot_id = base.parse_preflight(output)
    print(f'boot={boot_id}', flush=True)
    for name, (folder, digest) in FILES.items():
        data = (BUNDLES / folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f'changed binary: {name}')
        stage('172.16.42.1', '/tmp/' + name, data)
    before = snapshot(boot_id, directory, 'before-dwi')
    print(f"baseline DWI=0x{before['20120']:08x}", flush=True)
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        dwi_capture(sock, boot_id, directory / 'dwi.log')
    ready = snapshot(boot_id, directory, 'before-gpc')
    if ready['20120'] & 0xff != 0xff:
        raise ValueError('DWI not active at pre-GPC sample')
    print('DWI active; starting guarded GFX/GPC campaign', flush=True)
    # kpoll.run performs a second fresh-boot preflight and records a separate boot ID.
    def verify_dwi_before_request(current_boot):
        if current_boot != boot_id:
            raise ValueError('boot ID changed')
        output = remote("printf 'READ\\n' | /tmp/pmgr-words-peek 20120", boot_id,
                        directory / 'immediate-before-request-dwi.log')
        matches = re.findall(r'^w 0x020120 raw=0x([0-9a-f]{8})$', output, re.MULTILINE)
        if len(matches) != 1 or int(matches[0], 16) & 0xff != 0xff or \
                'stage=after-pmgr-words-read' not in output.splitlines():
            raise ValueError('DWI not active immediately before GPC')
    kpoll.run(directory / 'gpc-campaign', 'paired', expected_boot_id=boot_id,
              before_kpoll=verify_dwi_before_request)
    after = snapshot(boot_id, directory, 'after-gpc')
    time.sleep(10)
    late = snapshot(boot_id, directory, 'after-10s')
    print(f"DWI after GPC=0x{after['20120']:08x}; after 10s=0x{late['20120']:08x}")
    print(f'raw capture: {directory}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logdir', type=Path, help='new capture directory')
    args = parser.parse_args()
    try:
        run(args.logdir.resolve())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(1, f'campaign stopped: {error}; do not retry on this boot\n')


if __name__ == '__main__':
    main()
