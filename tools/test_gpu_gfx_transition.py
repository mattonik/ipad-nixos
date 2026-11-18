"""Checks the bounded per-boot recorder and its readiness controls."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from gpu_gfx_transition import CAPACITY, comparison, record

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
assert comparison(stock, linux)['comparison'] == 'same observed write values in order'
assert comparison(stock, record(stream([write, poll, end], 'linux'), 'linux'))['first_write_difference']['linux'] is None

assert record(stream([poll, write, poll, identity, end]), 'stock')['poll_control']['seq'] == 4
linux_other_history = record(stream([write, dict(poll, value=0xff), end], 'linux'), 'linux')
assert not linux_other_history['inconclusive'] and linux_other_history['poll_control']['value'] == '0x000000ff'
assert record(stream([write, dict(poll, value=0xef), end], 'linux'), 'linux')['inconclusive']
assert record(stream([write, dict(poll, value=0xff), identity, end]), 'stock')['inconclusive']

# With the same entry word and positive poll, ACTUAL can differ only in the last request.
active = dict(write, value=0xf)
ios_auto = dict(write, value=0x1000000f, old=None)
linux_auto = dict(write, value=0x100000ff, old=None)
ios_example = record(stream([active, poll, ios_auto, identity, end]), 'stock')
linux_example = record(stream([active, poll, linux_auto, end], 'linux'), 'linux')
diff = comparison(ios_example, linux_example)['first_write_difference']
assert diff['write_number'] == 2 and diff['xor'] == '0x000000f0'
assert diff['stock']['seq'] == diff['linux']['seq'] == 4
with_min = record(stream([dict(write, value=0), active, poll, ios_auto, identity, end]), 'stock')
assert comparison(with_min, linux_example)['first_write_difference']['write_number'] == 1

over = record(stream([write] * (CAPACITY + 1) + [poll, identity, end]), 'stock')
assert over['overflow'] and over['dropped'] == 2 and over['matched'] == CAPACITY + 2
assert over['poll_control'] and over['identity'] and comparison(over, linux) == dict(comparison='inconclusive', first_write_difference=None)
for events in ([poll, write, identity, end], [dict(write, thread='other'), poll, identity, end], [write, poll, end], [write, dict(poll, thread='other'), identity, end],
               [dict(write, instance=None), write, poll, identity, end], [write, poll, identity],
               [write, poll, identity, dict(end, lost=1)], [poll, identity, end]):
    assert comparison(record(stream(events), 'stock'), linux)['comparison'] == 'inconclusive'
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
    assert json.loads(output)['comparison'] == comparison(stock, linux)['comparison']
print('PASS: host GFX transition reports and coverage gates')
