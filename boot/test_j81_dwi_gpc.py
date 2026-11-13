#!/usr/bin/env python3
"""Exercise hold-campaign ordering and fail-closed gates without hardware."""
import tempfile
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import j81_dwi_gpc as campaign

BOOT = '12345678-1234-1234-1234-123456789abc'
if campaign.BUNDLE.exists():
    campaign.verify()
for name in ('gpu-pmgr-cycle-run', 'gpu-bridge-once-cycle-run', 'gpu-gpc-page5-kpoll-run'):
    import subprocess
    if not campaign.BUNDLE.exists(): continue
    subprocess.run(['sh', '-n', str(campaign.BUNDLE / name)], check=True)
    script = (campaign.BUNDLE / name).read_text()
    assert 'grep -qx j81_dwi_hold=1 || exit 1' in script
    assert script.index('grep -qx j81_dwi_hold=1') < script.index('/tmp/gpu-pmgr-peek || exit 1')


def scenario(fail=None):
    events = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'logs'
        bundle = Path(tmp) / 'bundle'; bundle.mkdir()
        files = {name: hashlib.sha256(name.encode()).hexdigest() for name in campaign.FILES}
        for name in files: (bundle / name).write_bytes(name.encode())
        (bundle / 'manifest.json').write_text(json.dumps({'kernel_notes': campaign.NOTES, 'files': files}))
        def stage(host, name, data):
            events.append('stage')
        def snapshot(boot, path):
            assert boot == BOOT
            name = path.stem
            events.append(name)
            if fail == name: raise RuntimeError('injected snapshot failure')
        def capture(function, *args, **kwargs):
            name = function.__module__.split('.')[-1]
            events.append(name)
            if fail == name: raise RuntimeError('injected capture failure')
            return {'mode': 'paired'}
        with patch.object(campaign, 'FILES', files), \
             patch.object(campaign, 'preflight', return_value=(BOOT, 'GO')), \
             patch.object(campaign, 'stage', side_effect=stage), \
             patch.object(campaign, 'snapshot', side_effect=snapshot), \
             patch.object(campaign, 'call_capture', side_effect=capture):
            if fail:
                try: campaign.run(path, bundle)
                except RuntimeError: pass
                else: raise AssertionError('failure accepted')
            else:
                assert campaign.run(path, bundle) == (BOOT, {'mode': 'paired'})
    return [e for e in events if e != 'stage']

assert scenario() == ['before-cycle', 'gpu_pmgr_cycle_capture', 'before-bridge',
                      'gpu_bridge_capture', 'before-gpc', 'gpu_gpc_page5_kpoll_capture', 'after-gpc']
assert scenario('before-cycle') == ['before-cycle']
assert scenario('gpu_pmgr_cycle_capture') == ['before-cycle', 'gpu_pmgr_cycle_capture']
assert scenario('before-gpc')[-1] == 'before-gpc'
assert 'gpu_gpc_page5_kpoll_capture' not in scenario('gpu_bridge_capture')

sample = 'stage=before-pmgr-words-read base=0x20e000000 words=3\nw 0x020120 raw=0x000000ff\nw 0x02300c raw=0x00000000\nw 0x005004 raw=0x00000000\nstage=after-pmgr-words-read'
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / 'sample'
    with patch.object(campaign.ipad_telnet_run, 'run', return_value=(sample, 0)):
        assert campaign.snapshot(BOOT, p) == sample
    for bad in (sample.replace('0x000000ff', '0x00000200'), sample.replace('stage=after-pmgr-words-read', '')):
        with patch.object(campaign.ipad_telnet_run, 'run', return_value=(bad, 0)):
            try: campaign.snapshot(BOOT, p)
            except RuntimeError: pass
            else: raise AssertionError('bad snapshot accepted')
print('PASS: bundle guards, test ordering and DWI/capture failures stop the campaign')

# The prepared wrappers must be reproducible from the pinned source files.
import prepare_j81_dwi_gpc as prepare
cycle = '/nix/store/51fsj23365sfm1579yb7fi8p8p8kq0k1-j81-dwi-gpu-pmgr-cycle-aarch64-unknown-linux-gnu-7.3.0-rc1/gpu-pmgr-cycle.ko'
kpoll = '/nix/store/yx4y6ckbz37cvszjjk26c36f5876nk74-j81-dwi-gpc-page5-kpoll-aarch64-unknown-linux-gnu-7.3.0-rc1/gpc-page5-kpoll.ko'
if campaign.BUNDLE.exists() and Path(cycle).is_file() and Path(kpoll).is_file() and prepare.KERNEL.is_file():
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / 'bundle'
        manifest = prepare.prepare(cycle, kpoll, output)
        assert manifest['files'] == campaign.FILES
        for name in campaign.FILES:
            assert (output / name).read_bytes() == (campaign.BUNDLE / name).read_bytes()
        try: prepare.prepare(cycle, kpoll, output)
        except FileExistsError: pass
        else: raise AssertionError('overwrote an existing bundle')
    print('PASS: exact bundle reproduced; existing bundles are never overwritten')
