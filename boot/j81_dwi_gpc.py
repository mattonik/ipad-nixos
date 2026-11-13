#!/usr/bin/env python3
"""Run one guarded GPC/page-5 comparison on the early-DWI-hold RAM boot."""
import argparse
import hashlib
import json
import re
import socket
from pathlib import Path

import gpu_bridge_capture
import gpu_gpc_page5_kpoll_capture as kpoll
import gpu_pmgr_cycle_capture
import ipad_telnet_run
from stage_gpu_test_bundle import stage

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / 'artifacts/live/private/j81-dwi-gpc-bundle-20261113'
NOTES = '5db452029d50cfaabd6cfb17f716509c895764543f87b7fee72709bca52aa9d0'
FILES = {
 'gfx-bridge-plan.bin':'1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435',
 'gpu-bridge-once':'3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c',
 'gpu-bridge-once-cycle-run':'f2a5392fde86fa1a421c5f1c6ac989d8bc4864e9038566d23517276de63721f2',
 'gpu-gpc-page5-kpoll-run':'b3968dfaf2bebd3729bbbd8b7cc5226ea56014f95e00bcbc9131b9113fc021b9',
 'gpu-pmgr-cycle-run':'71e2f55da3a206ae24a58cf581287b0f0bb9bef2f4148752572a9ca775e15f4a',
 'gpu-pmgr-cycle.ko':'c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23',
 'gpu-pmgr-peek':'78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd',
 'gpu-watchdog-supervisor':'9740666bb9c4aab798ca762416e0044b737b1f134970fa4b567db80fa3f60280',
 'j81-gpc-page5-kpoll.ko':'def7a657f995edf9b9d719ccc65cb9e15316a6394e463c02308c5b958dd82e59',
 'pmgr-words-peek':'b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502',
}
BOOT = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')


def verify(bundle=BUNDLE):
    record = json.loads((bundle / 'manifest.json').read_text())
    if record['kernel_notes'] != NOTES or record['files'] != FILES: raise ValueError('bundle manifest mismatch')
    for name, digest in FILES.items():
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != digest: raise ValueError('bundle changed: ' + name)
    return record


def preflight():
    cmd = r'''printf 'BOOT=%s\n' "$(cat /proc/sys/kernel/random/boot_id)";
    test "$(sha256sum /sys/kernel/notes | cut -d ' ' -f1)" = ''' + NOTES + r''' &&
    tr ' ' '\n' </proc/cmdline | grep -qx j81_dwi_hold=1 &&
    test "$(tr ' ' '\n' </proc/cmdline | grep -c '^j81_dwi_hold=')" = 1 &&
    test "$(cat /proc/device-tree/model)" = 'Apple iPad Air 2 (Wi-Fi)' &&
    tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,j81 &&
    grep -q '^rootfs / rootfs ' /proc/mounts && ! grep -q '^/dev/' /proc/mounts &&
    test -c /dev/watchdog0 && test -c /dev/mem &&
    test ! -e /sys/module/gpu_pmgr_cycle && test ! -e /sys/module/gpc_page5_kpoll &&
    test ! -e /sys/module/page5_read_once &&
    test ! -e /tmp/gpu-bridge-once.once && test ! -e /tmp/gpu-gpc-page5-kpoll.once &&
    test ! -e /tmp/gpu-gpc-init.once && test ! -e /tmp/gpu-gpc-page5-timed.once &&
    test ! -e /tmp/gpu-gpc-timed-revision.once && test ! -e /tmp/j81-page5-read-once.once &&
    dmesg | grep -q 'j81-dwi phase=off-rejected ret=-16' && echo GO'''
    out, rc = ipad_telnet_run.run(cmd, timeout=30)
    lines = out.splitlines()
    boot = [line[5:] for line in lines if line.startswith('BOOT=')]
    if rc or lines.count('GO') != 1 or len(boot) != 1 or not BOOT.fullmatch(boot[0]):
        raise RuntimeError('hold-boot preflight failed: ' + out)
    return boot[0], out


def snapshot(boot, path):
    if not BOOT.fullmatch(boot): raise ValueError('invalid boot ID')
    cmd = (f'test "$(cat /proc/sys/kernel/random/boot_id)" = {boot} && '
           f'test "$(sha256sum /tmp/pmgr-words-peek | cut -d " " -f1)" = {FILES["pmgr-words-peek"]} && '
           "printf 'READ\\n' | /tmp/pmgr-words-peek 20120 2300c 5004")
    out, rc = ipad_telnet_run.run(cmd, timeout=30)
    path.write_text(out + '\n')
    lines = out.splitlines()
    if rc or lines.count('stage=after-pmgr-words-read') != 1 or lines.count('w 0x020120 raw=0x000000ff') != 1:
        raise RuntimeError('DWI not confirmed on; stop this boot')
    if not all(sum(bool(re.fullmatch('w 0x' + off + r' raw=0x[0-9a-f]{8}', line)) for line in lines) == 1 for off in ('02300c', '005004')):
        raise RuntimeError('incomplete PMGR snapshot')
    return out


def call_capture(function, *args, **kwargs):
    with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
        return function(sock, *args, **kwargs)


def run(logdir, bundle=BUNDLE):
    verify(bundle)
    boot, output = preflight()
    logdir.mkdir(parents=True, exist_ok=False, mode=0o700)
    (logdir / 'preflight.log').write_text(output + '\n')
    for name in FILES:
        data = (bundle / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != FILES[name]: raise ValueError('bundle changed while staging')
        stage('172.16.42.1', '/tmp/' + name, data)
    snapshot(boot, logdir / 'before-cycle.log')
    call_capture(gpu_pmgr_cycle_capture.capture, logdir / 'cycle.log', FILES['gpu-pmgr-cycle.ko'], NOTES, 40)
    snapshot(boot, logdir / 'before-bridge.log')
    call_capture(gpu_bridge_capture.capture, logdir / 'bridge.log', FILES['gpu-bridge-once'],
                 (bundle / 'gfx-bridge-plan.bin').read_bytes(), 120, supervised=True,
                 supervisor_hash=FILES['gpu-watchdog-supervisor'], cycle_payload=True,
                 cycle_wrapper_hash=FILES['gpu-bridge-once-cycle-run'])
    snapshot(boot, logdir / 'before-gpc.log')
    result = call_capture(kpoll.capture, logdir / 'kpoll.log', FILES['j81-gpc-page5-kpoll.ko'],
                          FILES['gpu-watchdog-supervisor'], FILES['gpu-gpc-page5-kpoll-run'], boot, 'paired')
    snapshot(boot, logdir / 'after-gpc.log')
    return boot, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('new_log_directory', type=Path)
    args = parser.parse_args()
    try:
        boot, result = run(args.new_log_directory.resolve())
    except (OSError, KeyError, ValueError, RuntimeError) as e:
        parser.exit(1, f'campaign stopped: {e}; do not retry on this boot\n')
    print(f'boot={boot}')
    print('\n'.join(kpoll.describe(result)))
    print(f'capture={args.new_log_directory}')

if __name__ == '__main__': main()
