#!/usr/bin/env python3
"""Run one prepared J81 GPU experiment per fresh cycle-payload RAM boot."""
import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTES = '82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014'
MODULE = 'c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23'
SUPERVISOR = '093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f'
BRIDGE = '3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c'
BRIDGE_WRAPPER = '7d483501cd269e4fe0f24098bc5e4f08fd7206505091e367baaea6162e59f281'
GPC = '8a67ba955fca1aa2fe2b043e4512919aefa49c475542af1581d32b388f988282'
GPC_WRAPPER = '5c6ad81d26aa48d7361f9a47de9117abcc3e431b5ab7fe93fc8805732cf5ce1f'
TIMED = 'a489491f0dc9e285f9fb6adcdc3b05d2fcf7f86921fa53464cbefba0781728ea'
CORE = '2dbaa48a8683a3164fd69b1d43aaeb518e81d66d0b942170196893a023e1f1b3'
TIMED_WRAPPER = '55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09'
PLAN = '1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435'
PEEK = '78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd'
CYCLE_WRAPPER = 'e21f678dd41064d865b9946a0a6c9002166ea573ed48500e9748fe0e0e848d62'


def verify_bundle(bundle, mode):
    names = {
        'bin/gpu-pmgr-peek': PEEK, 'bin/gpu-bridge-once': BRIDGE,
        'bin/gpu-watchdog-supervisor': SUPERVISOR, 'modules/gpu-pmgr-cycle.ko': MODULE,
        'data/gfx-bridge-plan.bin': PLAN, 'wrappers/gpu-pmgr-cycle-run.sh': CYCLE_WRAPPER,
        'wrappers/gpu-bridge-once-cycle-run.sh': BRIDGE_WRAPPER,
    }
    if mode in ('gpc-control', 'paced'):
        names.update({'bin/gpu-gpc-init': GPC, 'wrappers/gpu-gpc-init-cycle-run.sh': GPC_WRAPPER})
    if mode == 'paced':
        names.update({'bin/gpu-core-revision-once': CORE,
                      'wrappers/gpu-core-revision-once-cycle-run.sh': TIMED_WRAPPER})
    elif mode == 'timed':
        names.update({'bin/gpu-core-revision-once': TIMED,
                      'wrappers/gpu-core-revision-once-cycle-run.sh': TIMED_WRAPPER})
    manifest = json.loads((bundle / 'MANIFEST.json').read_text())
    for name, expected in names.items():
        group, item = name.split('/', 1)
        entry = manifest['binaries' if group == 'bin' else group][item]
        if entry['sha256'] != expected or hashlib.sha256((bundle / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'bundle checksum mismatch: {name}')
    return list(names)


def parse_preflight(output):
    lines = output.replace('\r', '').split('\n')
    ids = [m.group(1) for line in lines if (m := re.fullmatch(r'CAMPAIGN_BOOT=([0-9a-f-]{36})', line))]
    if lines.count('CAMPAIGN_GOOD') != 1 or lines.count('CAMPAIGN_END') != 1 or len(ids) != 1:
        raise ValueError('fresh RAM-boot preflight did not pass')
    return ids[0]


def preflight():
    command = ("gfx=/sys/firmware/devicetree/base/soc/power-management@20e000000/power-controller@20320; "
               "printf 'CAMPAIGN_BOOT=%s\\n' \"$(cat /proc/sys/kernel/random/boot_id)\"; "
               "if tr '\\0' '\\n' < \"$gfx/compatible\" | grep -qx apple,t7000-pmgr-pwrstate; then "
               "if test ! -e \"$gfx/experimental,j81-gpu-test-no-poweroff\" && "
               f"test \"$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)\" = {NOTES} && "
               "grep -q '^rootfs / rootfs ' /proc/mounts && ! grep -q '^/dev/' /proc/mounts && "
               "test ! -e /sys/module/gpu_pmgr_cycle && test ! -e /tmp/gpu-bridge-once.once && "
               "test ! -e /tmp/gpu-gpc-init.once && test ! -e /tmp/gpu-gpc-timed-revision.once; "
               "then printf 'CAMPAIGN_%s\\n' GOOD; fi; fi; printf 'CAMPAIGN_%s\\n' END\n")
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        sock.settimeout(.5)
        sock.sendall(command.encode())
        data = b''
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(8192)
                if not chunk: break
                data += chunk
            except TimeoutError:
                pass
            if b'\nCAMPAIGN_END\r\n' in data: break
            if len(data) > 65536: raise ValueError('preflight output too large')
    return data.decode(errors='replace')


def commands(mode, bundle, logdir, names):
    stage = [sys.executable, 'boot/stage_gpu_test_bundle.py', '--bundle', str(bundle), *names]
    cycle = [sys.executable, 'boot/gpu_pmgr_cycle_capture.py', str(logdir / 'pmgr.log'), MODULE, NOTES]
    bridge = [sys.executable, 'boot/gpu_bridge_capture.py', str(logdir / 'bridge.log'), BRIDGE,
              str(bundle / 'data/gfx-bridge-plan.bin'), '--supervised', '--supervisor-sha256', SUPERVISOR,
              '--cycle-payload', '--cycle-wrapper-sha256', BRIDGE_WRAPPER]
    steps = [('stage', stage), ('pmgr', cycle), ('bridge', bridge)]
    if mode in ('gpc-control', 'paced'):
        gpc = [sys.executable, 'boot/gpu_gpc_init_capture.py', str(logdir / 'gpc.log'), GPC,
               '--supervised', '--supervisor-sha256', SUPERVISOR, '--wrapper-sha256', GPC_WRAPPER]
        steps.append(('gpc', gpc))
    if mode == 'paced':
        core = [sys.executable, 'boot/gpu_core_revision_capture.py', str(logdir / 'core.log'), CORE,
                '--supervisor-sha256', SUPERVISOR, '--wrapper-sha256', TIMED_WRAPPER]
        steps.append(('core', core))
    if mode == 'timed':
        timed = [sys.executable, 'boot/gpu_gpc_timed_revision_capture.py', str(logdir / 'timed.log'), TIMED,
                 '--supervisor-sha256', SUPERVISOR, '--wrapper-sha256', TIMED_WRAPPER]
        steps.append(('timed', timed))
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('gpc-control', 'paced', 'timed'))
    parser.add_argument('logdir', type=Path, help='new, unique directory for this boot')
    args = parser.parse_args()
    bundle = ROOT / ('artifacts/live/gpu-test-bundle-20261107-core-revision' if args.mode == 'paced'
                     else 'artifacts/live/gpu-test-bundle-timed-revision-v3')
    try:
        names = verify_bundle(bundle, args.mode)
        args.logdir = args.logdir.resolve()
        args.logdir.mkdir(parents=True, exist_ok=False)
        output = preflight()
        (args.logdir / 'preflight.log').write_text(output)
        boot = parse_preflight(output)
        print(f'boot={boot} mode={args.mode}', flush=True)
        for name, command in commands(args.mode, bundle, args.logdir, names):
            print(f'running {name}', flush=True)
            with (args.logdir / (name + '-runner.log')).open('x') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{name} failed (exit {result.returncode}); stop for this boot')
        print(f'complete: {args.logdir}', flush=True)
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        parser.exit(1, f'campaign stopped: {error}; do not retry on this boot\n')


if __name__ == '__main__':
    main()
