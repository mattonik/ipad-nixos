#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

import touch_fw_rebuild as r


def synthetic(n=64, addr=0):
    return r.build(bytes((i * 7 + 3) & 0xFF for i in range(n)), addr)


class RebuildTests(unittest.TestCase):
    def test_roundtrip(self):
        pkt = synthetic(256)
        payload, addr = r.parse(pkt)
        self.assertEqual((len(payload), addr), (256, 0))
        self.assertEqual(r.build(payload, addr), pkt)

    def test_header_constants(self):
        pkt = synthetic(8, 0x10001c04)
        self.assertEqual(pkt[:4], b"\x18\xe1\x30\x01")
        self.assertEqual(pkt[4:6], (2).to_bytes(2, "big"))           # two 32-bit words
        self.assertEqual(pkt[6:10], bytes([0x1c, 0x04, 0x10, 0x00]))  # halves swapped
        self.assertEqual(len(pkt), 8 + 16)

    def test_slice_gets_offset_as_destination(self):
        pkt = synthetic(256)
        small = r.rebuild(pkt, 64, 128)
        payload, addr = r.parse(small)
        self.assertEqual(addr, 128)
        self.assertEqual(payload, r.parse(pkt)[0][128:192])
        self.assertEqual(len(small), 64 + 16)

    def test_full_rebuild_is_identical(self):
        pkt = synthetic(1024)
        self.assertEqual(r.rebuild(pkt, 1024, 0), pkt)

    def test_rejects_corruption_and_bad_sizes(self):
        pkt = bytearray(synthetic(64))
        bad = bytes(pkt[:20]) + bytes([pkt[20] ^ 1]) + bytes(pkt[21:])
        with self.assertRaises(ValueError):
            r.parse(bad)
        with self.assertRaises(ValueError):
            r.rebuild(bytes(pkt), 6, 0)
        with self.assertRaises(ValueError):
            r.rebuild(bytes(pkt), 64, 4)
        with self.assertRaises(ValueError):
            r.build(b"", 0)

    def test_cli_writes_private_files_without_overwriting(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "p.bin"
            src.write_bytes(synthetic(128))
            out = Path(d) / "out"
            self.assertEqual(r.main([str(src), str(out), "64", "32@64"]), 0)
            self.assertEqual((out / "pkt-64@0.bin").stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                r.main([str(src), str(out), "64"])


if __name__ == "__main__":
    unittest.main()
