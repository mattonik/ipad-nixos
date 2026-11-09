#!/usr/bin/env python3
"""Test the paired capture sequence without a device."""
from pathlib import Path
import hashlib
import socket
import tempfile
from unittest.mock import patch
import gpu_pmgr_perf_pair as pair

class DummySocket:
    def __enter__(self): return self
    def __exit__(self, *args): return False


def test_sequence(mode):
    calls = []
    original_boot = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    def get_boot():
        calls.append('boot')
        if mode == 'reboot' and calls.count('boot') == 3:
            return '11111111-2222-3333-4444-555555555555'
        return original_boot
    def snapshot(path, expected):
        calls.append(f'snapshot:{expected:x}')
        if mode == 'bad-before' and expected == 0x300:
            raise RuntimeError('unexpected PMGR state')
        return {'ps': expected, 'ctl': 0x80000000}
    def request_power(*args):
        calls.append('power')
        if mode == 'bad-power': raise RuntimeError('power attempt failed')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'capture'
        artifact = Path(tmp) / 'artifact'
        artifact.write_bytes(b'test-only')
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        files = {name: (str(artifact), digest) for name in pair.FILES}
        with patch.object(pair.subprocess, 'run'), patch.object(pair, 'boot_id', get_boot), \
             patch.object(pair, 'FILES', files), \
             patch.object(pair, 'stage', lambda *args: calls.append('stage')), \
             patch.object(pair, 'read_snapshot', snapshot), \
             patch.object(pair.power, 'capture', request_power), \
             patch.object(socket, 'create_connection', lambda *a, **k: DummySocket()), \
             patch.object(pair.time, 'sleep'):
            try:
                pair.execute(path)
                assert mode == 'ok'
            except RuntimeError:
                assert mode != 'ok'
        if mode == 'ok': assert calls.count('power') == 1 and 'snapshot:3ff' in calls
        if mode in ('bad-before', 'reboot'): assert 'power' not in calls
        if mode == 'bad-power': assert 'snapshot:3ff' not in calls

for mode in ('ok', 'bad-before', 'bad-power', 'reboot'):
    test_sequence(mode)

names = ['ps', 'ctl', 'w300'] + [f'perf{n:02d}{s}' for n in range(16) for s in ('', '+4')]
data = ''.join(f'{n} raw=0x00000000\n' for n in names).encode()
assert pair.perf.complete_output(data)
assert not pair.perf.complete_output(data + b'ctl raw=0x00000000\n')
assert not pair.perf.complete_output(data.replace(b'w300 raw=0x00000000\n', b''))
print('PASS: paired capture fails closed and accepts archived labels')
