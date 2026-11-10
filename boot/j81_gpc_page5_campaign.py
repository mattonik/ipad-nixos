#!/usr/bin/env python3
"""Run the guarded PMGR/bridge setup and one immediate GPC/page-5 sample."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path
import gpu_campaign as campaign
import gpu_gpc_page5_timed_capture as timed
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'artifacts/live/gpu-test-bundle-timed-revision-v3'
BUNDLE = ROOT / 'artifacts/live/private/j81-gpc-page5-timed-bundle-v2'
FILES = {
    'gpu-gpc-page5-timed': '7ed55c603bf6c20298e18621e1defbb199cca2cef541819c8a092009a05ea6b5',
    'gpu-gpc-page5-timed-run': '84da3a1de46a79a7b55beec8b029e6e99bb4c0aa6d3ce49a415c8cae196d7c95',
    'gpu-watchdog-supervisor': 'e7be98e9b60842cb8618eb4e1945912ad01374bfb1d32be32bc0dfdff014d08e',
    'j81-page5-read-once.ko': 'ca16576e6d574ff3587d631cd3fb82e3ae0ce83f49cdd5c4d3156f9306099e4c',
}


def verify():
    names = campaign.verify_bundle(BASE, 'gpc-control')
    for name, expected in FILES.items():
        if hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'bundle checksum mismatch: {name}')
    return names


def run(logdir):
    names = verify()
    logdir.mkdir(parents=True, exist_ok=False)
    output = campaign.preflight(); (logdir / 'preflight.log').write_text(output)
    boot_id = campaign.parse_preflight(output)
    print(f'boot={boot_id} mode=gpc-page5-timed', flush=True)
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
    import socket
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        value = timed.capture(sock, logdir / 'timed.log', FILES['gpu-gpc-page5-timed'],
                              FILES['gpu-watchdog-supervisor'], FILES['gpu-gpc-page5-timed-run'], boot_id)
    print(f'page5=0x{value:08x}; capture={logdir}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('logdir', type=Path); a = p.parse_args()
    try: run(a.logdir.resolve())
    except (OSError, KeyError, ValueError, RuntimeError) as e: p.exit(1, f'campaign stopped: {e}; do not retry on this boot\n')
if __name__ == '__main__': main()
