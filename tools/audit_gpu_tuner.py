#!/usr/bin/env python3
"""Audit captured J81 tuner membership and model the static Apple policy."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from audit_gpu_bridge_plan import blob, capture_table, child


def mode(a, b, display, audio):
    if not display:
        return int(bool(audio))
    return 3 if not a and not b else 2


def block(text, compatible):
    blocks = [part for part in re.split(r'(?m)^-{5,}\s*$', text)
              if re.search(r'(?m)^\s*compatible\s+' + re.escape(compatible) + r'\s*$', part)]
    if len(blocks) != 1:
        raise ValueError('missing or ambiguous ' + compatible)
    return blocks[0]


def scalar(text, name):
    matches = re.findall(r'(?m)^\s*' + re.escape(name) + r'\s+(0x[0-9a-fA-F]+)\s*$', text)
    if len(matches) != 1:
        raise ValueError('missing or ambiguous ' + name)
    return int(matches[0], 16)


def audit(text):
    pmgr = block(text, 'pmgr1,t7001')
    tuner = block(text, 'soc-tuner,t7000')
    records = capture_table(pmgr, 'devices')
    if len(records) % 48:
        raise ValueError('invalid PMGR records')
    names = {}
    for i in range(0, len(records), 48):
        record = records[i:i+48]
        if record[3] in names:
            raise ValueError('duplicate device ID')
        names[record[3]] = record[32:48].split(b'\0')[0].decode('ascii')
    sets = []
    for index in range(4):
        prop = f'device-set-{index}'
        data = capture_table(tuner, prop)
        if data:
            if len(data) % 4 or len(data) > 128:
                raise ValueError('invalid device set')
            ids = [x[0] for x in struct.iter_unpack('<I', data)]
        else:
            ids = [scalar(tuner, prop)]
        sets.append(ids)
    if (scalar(tuner, '#device-sets') != 4 or scalar(tuner, 'fb-caching') != 1 or
        sets[0] != [0x12, 0x18, 0x1d, 0x74, 0x7c] or sets[2] != [0x1c] or
        names.get(0x7c) != 'GFX' or names.get(0x1c) != 'DISP0'):
        raise ValueError('unexpected tuner topology')
    configs = capture_table(tuner, 'mcc-configs')
    if len(configs) != 16:
        raise ValueError('unexpected configuration list')
    configs = [x[0] for x in struct.iter_unpack('<I', configs)]
    if configs != [1, 2, 3, 4]:
        raise ValueError('unexpected configuration list')
    mcc_data = capture_table(block(text, 'mcc,t7000'), 'config-data')
    if len(mcc_data) != 5 * 44:
        raise ValueError('unexpected MCC configuration table length')
    rows = [mcc_data[i:i+44] for i in range(0, len(mcc_data), 44)]
    return {'mcc_sha256': hashlib.sha256(mcc_data).hexdigest(),
            'mcc_configs_3_and_4_identical': rows[3] == rows[4],
            'sets': [[{'id': hex(i), 'name': names.get(i, 'unknown')} for i in group] for group in sets],
            'gfx_bit': 4, 'display_bit': 0, 'display_and_gfx_mode': mode(16, 0, 1, 0),
            'display_and_gfx_config': configs[mode(16, 0, 1, 0)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--ios81-tree', type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.capture.read_text())
        if args.ios81_tree:
            root = json.loads(args.ios81_tree.read_text())['device-tree']
            older = blob(child(child(root, 'arm-io'), 'mcc')['config-data'])
            result['ios81_table_matches'] = hashlib.sha256(older).hexdigest() == result['mcc_sha256']
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, UnicodeError) as error:
        parser.exit(1, f'audit failed: {error}\n')


if __name__ == '__main__':
    main()
