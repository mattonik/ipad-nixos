#!/usr/bin/env python3
"""Check the tuner's captured topology and state-decision model."""
import itertools
import struct
import unittest
from audit_gpu_tuner import audit, mode


def fixture():
    def row(data):
        return ' '.join(f'{x:02x}' for x in data)
    devices = b''
    for ident, name in [(0x12,'MEDIA'),(0x18,'ISP'),(0x1d,'DISP1'),(0x74,'DISP-FB-ACTIVE'),
                        (0x7c,'GFX'),(0x1c,'DISP0'),(0x6d,'CPU-BUSY')]:
        rec = bytearray(48)
        rec[3] = ident
        rec[32:32+len(name)] = name.encode()
        devices += rec
    word = lambda values: row(b''.join(struct.pack('<I', x) for x in values))
    return '\n'.join([' compatible pmgr1,t7001', ' devices ' + row(devices), '-----',
                      ' compatible soc-tuner,t7000', ' #device-sets 0x00000004',
                      ' fb-caching 0x00000001', ' device-set-0 ' + word([0x12,0x18,0x1d,0x74,0x7c]),
                      ' device-set-1 0x0000006d', ' device-set-2 0x0000001c',
                      ' device-set-3 ' + word([0x40,0x41,0x42,0x43,0x44]),
                      ' mcc-configs ' + word([1,2,3,4]), '-----',
                      ' compatible mcc,t7000', ' config-data ' + word([0]*55)])


class TestTuner(unittest.TestCase):
    def test_modes(self):
        for a,b,c,d in itertools.product((0,1), repeat=4):
            self.assertEqual(mode(a,b,c,d), (2 if a or b else 3) if c else d)
        self.assertEqual(mode(16,0,1,0), 2)

    def test_topology_and_changes(self):
        text = fixture()
        self.assertEqual(audit(text)['display_and_gfx_config'], 3)
        self.assertTrue(audit(text)['mcc_configs_3_and_4_identical'])
        prefix, data = text.split(' config-data ')
        values = data.split()
        values[4 * 44] = '01'
        self.assertFalse(audit(prefix + ' config-data ' + ' '.join(values))['mcc_configs_3_and_4_identical'])
        for changed in (text.replace('fb-caching 0x00000001','fb-caching 0x00000000'),
                        text.replace('device-set-2 0x0000001c','device-set-2 0x0000001d'),
                        text + '\n' + text):
            with self.assertRaises(ValueError):
                audit(changed)


if __name__ == '__main__':
    unittest.main()
