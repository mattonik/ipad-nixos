#!/usr/bin/env python3
"""Run the guarded PMGR/bridge setup, then one in-kernel GPC poll and page-5 sample."""
import argparse
import hashlib
import socket
import subprocess
from pathlib import Path
import gpu_campaign as campaign
import gpu_gpc_page5_kpoll_capture as kpoll
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/live/gpu-test-bundle-timed-revision-v3'
BUNDLE = ROOT / 'artifacts/live/private/j81-gpc-page5-kpoll-bundle-v1'
# SHA-256 of the exact files built for this test; None means "not built yet".
FILES = {
    'j81-gpc-page5-kpoll.ko': None,
    'gpu-gpc-page5-kpoll-run': None,
    'gpu-watchdog-supervisor': None,
}


def verify():
    if not all(FILES.values()): raise ValueError('test bundle is not pinned yet')
    names = campaign.verify_bundle(BASE, 'gpc-control')
    for name, expected in FILES.items():
        if hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'bundle checksum mismatch: {name}')
    return names


def run(logdir, mode):
    if mode not in kpoll.MODES: raise ValueError('invalid mode')
    names = verify()
    logdir.mkdir(parents=True, exist_ok=False)
    output = campaign.preflight(); (logdir / 'preflight.log').write_text(output)
    boot_id = campaign.parse_preflight(output)
    print(f'boot={boot_id} mode=gpc-page5-kpoll/{mode}', flush=True)
    for name, command in campaign.commands('gpc-control', BASE, logdir, names)[:3]:
        print(f'running {name}', flush=True)
        with (logdir / (name + '-runner.log')).open('x') as log:
            if subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode:
                raise RuntimeError(f'{name} failed; stop for this boot')
    for name in FILES:
        print(f'staging {name}', flush=True)
        data = (BUNDLE / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != FILES[name]: raise ValueError(f'bundle changed: {name}')
        stage('172.16.42.1', '/tmp/' + name, data)
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        result = kpoll.capture(sock, logdir / 'kpoll.log', FILES['j81-gpc-page5-kpoll.ko'],
                               FILES['gpu-watchdog-supervisor'], FILES['gpu-gpc-page5-kpoll-run'], boot_id, mode)
    print('\n'.join(kpoll.describe(result)), flush=True)
    print(f'capture={logdir}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=kpoll.MODES); p.add_argument('logdir', type=Path); a = p.parse_args()
    try: run(a.logdir.resolve(), a.mode)
    except (OSError, KeyError, ValueError, RuntimeError) as e: p.exit(1, f'campaign stopped: {e}; do not retry on this boot\n')
if __name__ == '__main__': main()
