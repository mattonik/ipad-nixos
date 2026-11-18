"""Checks the bounded per-boot recorder and its readiness controls."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from gpu_gfx_transition import CAPACITY, compare, record

write = dict(kind='write', region=0, offset=0x20320, instance=0, phase='clock',
             thread='same', caller='state setter', old=0x300, value=0x30f)
poll = dict(write, kind='poll', value=0x3ff)
identity = dict(kind='identity', value=0x70500)
end = dict(kind='end', lost=0)


def stream(events, role='stock'):
    return [json.dumps(e) for e in [dict(kind='boot', role=role, boot='synthetic'), *events]]


before = [dict(write, offset=4)] * 135 + [dict(write, instance=1)]
ordered = [*before, write, dict(write, thread='other', old=None), poll, identity, end]
stock = record(stream(ordered), 'stock')
assert not stock['inconclusive'] and stock['matched'] == stock['stored'] == 3
assert stock['rows'][0]['old'] == '0x00000300' and stock['rows'][0]['seq'] == 138
assert stock['rows'][1]['thread'] == 'other' and stock['rows'][1]['old'] is None
linux = record(stream(ordered[:-2] + [end], 'linux'), 'linux')
assert compare(stock, linux) == 'same observed write values in order'
assert compare(stock, record(stream([write, poll, end], 'linux'), 'linux')).startswith('different')

over = record(stream([write] * (CAPACITY + 1) + [poll, identity, end]), 'stock')
assert over['overflow'] and over['dropped'] == 2 and over['matched'] == CAPACITY + 2
assert over['poll_control'] and over['identity'] and compare(over, linux) == 'inconclusive'
for events in ([poll, write, identity, end], [dict(write, thread='other'), poll, identity, end], [write, poll, end], [write, dict(poll, thread='other'), identity, end],
               [dict(write, instance=None), write, poll, identity, end], [write, poll, identity],
               [write, poll, identity, dict(end, lost=1)], [poll, identity, end]):
    assert compare(record(stream(events), 'stock'), linux) == 'inconclusive'
for malformed in ([write, end, poll], [dict(write, value=True)], [dict(write, instance=0x80000000)]):
    try:
        record(stream(malformed), 'stock')
    except ValueError:
        continue
    raise AssertionError('malformed input accepted')
with TemporaryDirectory() as d:
    paths = []
    for role in ('stock', 'linux'):
        path = Path(d) / role
        path.write_text('\n'.join(stream(ordered, role)) + '\n')
        paths.append(path)
    output = subprocess.check_output([sys.executable, str(Path(__file__).with_name('gpu_gfx_transition.py')), *paths])
    assert json.loads(output)['comparison'] == compare(stock, linux)
print('PASS: host GFX transition reports and coverage gates')
