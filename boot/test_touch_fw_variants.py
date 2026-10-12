#!/usr/bin/env python3
import unittest

import touch_fw_rebuild as r
import touch_fw_variants as v


def real_packet():
    return r.build(bytes((i * 7 + 3) & 0xFF for i in range(2048)), 0)


class VariantTests(unittest.TestCase):
    def test_zero(self):
        p = v.zero(64)
        self.assertEqual((len(p), p[:2], set(p[2:])), (64, b"\x18\xe1", {0}))

    def test_badsum_is_wrong_only_in_the_header_sum(self):
        good = r.rebuild(real_packet(), 1024, 0)
        bad = v.badsum(real_packet(), 1040)
        self.assertEqual(len(bad), 1040)
        self.assertEqual(bad[:10], good[:10])
        self.assertNotEqual(bad[10:12], good[10:12])
        self.assertEqual(bad[12:], good[12:])
        with self.assertRaises(ValueError):
            r.parse(bad)

    def test_declared_length_mismatch(self):
        p = v.declared(real_packet(), 80, 14818)
        self.assertEqual(len(p), 80)
        self.assertEqual(int.from_bytes(p[4:6], "big"), 14818)
        self.assertEqual(int.from_bytes(p[10:12], "big"), r.hdr_sum(p[4:10]))   # header sum valid for the declared length
        with self.assertRaises(ValueError):
            r.parse(p)                                                          # but the packet length does not match
        q = v.declared(real_packet(), 2064, 16)
        self.assertEqual((len(q), int.from_bytes(q[4:6], "big")), (2064, 16))


if __name__ == "__main__":
    unittest.main()
