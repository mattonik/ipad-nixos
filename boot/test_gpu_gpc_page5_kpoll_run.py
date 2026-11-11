#!/usr/bin/env python3
"""Run the wrapper's acknowledged protocol against fake sysfs files; check its guards by text."""
import subprocess
import tempfile
from pathlib import Path

script = Path(__file__).with_name('gpu-gpc-page5-kpoll-run.sh')
text = script.read_text()
guards, protocol = text.split('# --- host-acknowledged protocol', 1)
protocol = protocol.split('\n', 1)[1]
OK = ('result=ok mode=immediate raw=0x00000001 polls=5 prewrite_ns=300000 postwrite_ns=299000 '
      'first_valid=1 first=0x40000000 first_ns=250 later_valid=0 later=0x00000000 later_ns=0')

# Every guard precedes the first device access, and the module is loaded last.
order = ['random/boot_id', 'uname -r', 'j81-gpc-page5-kpoll.ko | cut', '/sys/kernel/notes', 'gpu_pmgr_cycle/notes',
         'apple,j81', 'runtime_status', 'runtime_usage', "'^rootfs / rootfs '", '.once" ] || exit 1',
         '/sys/module/gpc_page5_kpoll', '/tmp/gpu-pmgr-peek || exit 1', 'mkdir /tmp/gpu-gpc-page5-kpoll.once', '/sbin/insmod']
positions = [guards.index(item) for item in order]
assert positions == sorted(positions), positions
assert 'insmod' not in protocol and '/dev/mem' not in text and 'echo ' not in text and ' > ' not in text
for bad in (['a' * 64, 'x', 'immediate'], ['a' * 63, '12345678-1234-1234-1234-123456789abc', 'paired'],
            ['a' * 64, '12345678-1234-1234-1234-123456789abc', 'write'], ['a' * 64]):
    assert subprocess.run(['sh', str(script), *bad], capture_output=True).returncode == 2, bad


def run(state, batch, replies, mode='immediate'):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / 'gpc_state').write_text(state)
        if batch is not None: (d / 'batch').write_text(batch)
        else: (d / 'batch').mkdir()  # readable test passes, cat fails
        body = f'set -u\nmode={mode}\ndev={d}\n' + protocol
        r = subprocess.run(['sh', '-c', body], input=replies, capture_output=True, text=True)
        return r.returncode, r.stdout.splitlines()


rc, out = run('address=0x201e01000 value=0x00000000\n', OK + '\n', 'READ\nREAD\n')
assert rc == 0 and out == [
    'stage=before-gpc-state address=0x201e01000 width=32', 'stage=after-gpc-state raw=0x00000000',
    'stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=immediate', 'checkpoint=before-kernel-batch',
    'checkpoint=kernel-batch ' + OK, 'stage=after-gpc-page5-kpoll ' + OK, 'stage=finished rc=0'], out
# No acknowledgement: nothing is read.
rc, out = run('address=0x201e01000 value=0x00000000\n', OK + '\n', '')
assert rc == 1 and out == ['stage=before-gpc-state address=0x201e01000 width=32'], out
rc, out = run('address=0x201e01000 value=0x00000000\n', OK + '\n', 'READ\nACCESS\n')
assert rc == 1 and out[-1].startswith('stage=before-gpc-page5-kpoll') and len(out) == 3, out
# GPC not initially zero: reported, batch never read.
rc, out = run('address=0x201e01000 value=0x00000001\n', OK + '\n', 'READ\nREAD\n')
assert rc == 1 and out[1:] == ['stage=after-gpc-state raw=0x00000001', 'stage=finished rc=1'], out
rc, out = run('garbage\n', OK + '\n', 'READ\nREAD\n')
assert rc == 1 and len(out) == 1, out
# Poll failure keeps the raw value and count; a mode mismatch or read error fails.
fail = 'result=poll-failed mode=immediate raw=0x00000011 polls=1000'
rc, out = run('address=0x201e01000 value=0x00000000\n', fail + '\n', 'READ\nREAD\n')
assert rc == 1 and out[-2:] == ['checkpoint=kernel-batch ' + fail, 'stage=finished rc=1'], out
rc, out = run('address=0x201e01000 value=0x00000000\n', OK + '\n', 'READ\nREAD\n', mode='paired')
assert rc == 1 and out[-1] == 'stage=finished rc=1' and not any(l.startswith('stage=after-gpc-page5') for l in out), out
rc, out = run('address=0x201e01000 value=0x00000000\n', None, 'READ\nREAD\n')
assert rc == 1 and out[-2:] == ['checkpoint=kernel-batch-read-failed', 'stage=finished rc=1'], out
print('PASS: wrapper guard order, acknowledgements, state gate, poll failure and read error')
