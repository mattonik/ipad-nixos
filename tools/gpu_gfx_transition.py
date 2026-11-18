#!/usr/bin/env python3
"""Record and compare J81 GFX observations from saved per-boot JSONL streams."""
import argparse
import json
from pathlib import Path

TARGET = (0, 0x20320, 0)
CAPACITY = 32


def uint(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError("expected an unsigned 32-bit JSON integer")
    return value


def word(value):
    return f"0x{uint(value):08x}"


def record(lines, role):
    rows = []
    matched = 0
    positive = identity = boot = upstream_lost = None
    unknown_instance = 0
    same_thread_write = False
    for seq, line in enumerate(lines, 1):
        try:
            e = json.loads(line)
            kind = e['kind']
            if seq == 1:
                if kind != 'boot' or e['role'] != role or not isinstance(e['boot'], str) or not e['boot'].strip():
                    raise ValueError(f"expected {role} boot header")
                boot = e['boot']
                continue
            if upstream_lost is not None:
                raise ValueError("data after end record")
            if kind == 'end':
                upstream_lost = uint(e['lost'])
                continue
            if kind == 'identity':
                if identity is not None:
                    raise ValueError("multiple identity observations")
                identity = dict(seq=seq, value=word(e['value']))
                continue
            if identity is not None:
                raise ValueError("trace window extends past identity result")
            if kind not in ('write', 'poll'):
                raise ValueError("unexpected observation kind")
            region, offset = uint(e['region']), uint(e['offset'])
            instance = e['instance']
            if instance is not None:
                instance = uint(instance)
                if instance == 0x80000000:
                    raise ValueError("synthetic export tag cannot stand for instance")
            if (region, offset) == TARGET[:2] and instance is None:
                unknown_instance += 1
            if (region, offset, instance) != TARGET:
                continue
            phase, thread = e['phase'], e['thread']
            if phase not in ('before', 'clock', 'power', 'unknown') or thread not in ('same', 'other', 'unknown'):
                raise ValueError("invalid phase or thread")
            caller = e.get('caller')
            if caller is not None and (not isinstance(caller, str) or not caller.strip()):
                raise ValueError("caller must be a nonempty string or null")
            row = dict(seq=seq, kind=kind, phase=phase, thread=thread, caller=caller, value=word(e['value']))
            if kind == 'write':
                row['old'] = None if e.get('old') is None else word(e['old'])
                if thread == 'same':
                    same_thread_write = True
            elif positive is None and thread == 'same' and same_thread_write:
                # Stock has an exact published control. Linux can reach ACTIVE with different history bits.
                if (role == 'stock' and e['value'] == 0x3ff) or (role == 'linux' and e['value'] & 0xf0 == 0xf0):
                    positive = row
            matched += 1
            if len(rows) < CAPACITY:
                rows.append(row)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"line {seq}: {exc}") from exc
    if boot is None:
        raise ValueError('missing boot header')
    reasons = []
    if upstream_lost is None or upstream_lost:
        reasons.append('source coverage incomplete')
    if matched > len(rows):
        reasons.append('target buffer overflow')
    if unknown_instance:
        reasons.append('target offset observed with unknown instance')
    if positive is None:
        expected = '0x3ff' if role == 'stock' else 'ACTUAL=15'
        reasons.append(f'missing same-thread write followed by {expected} poll')
    if role == 'stock' and (identity is None or identity['value'] != '0x00070500' or
                            positive is None or identity['seq'] <= positive['seq']):
        reasons.append('missing working identity after positive poll')
    if not any(row['kind'] == 'write' for row in rows):
        reasons.append('no target write observed')
    return dict(boot=boot, matched=matched, stored=len(rows), dropped=matched-len(rows),
                overflow=matched > len(rows), upstream_lost=upstream_lost,
                unknown_instance=unknown_instance, poll_control=positive, identity=identity,
                rows=rows, inconclusive=reasons)


def compare(stock, linux):
    if stock['inconclusive'] or linux['inconclusive']:
        return 'inconclusive'
    def requested(report):
        return [row['value'] for row in report['rows'] if row['kind'] == 'write']
    return 'same observed write values in order' if requested(stock) == requested(linux) else 'different observed write values or order'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('linux', type=Path, nargs='?')
    args = parser.parse_args()
    try:
        with args.stock.open() as stream:
            reports = {'stock': record(stream, 'stock')}
        if args.linux:
            with args.linux.open() as stream:
                reports['linux'] = record(stream, 'linux')
            reports['comparison'] = compare(reports['stock'], reports['linux'])
        print(json.dumps(reports, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')
