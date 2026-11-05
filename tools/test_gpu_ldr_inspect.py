#!/usr/bin/env python3
"""Exercise LDR inspection on synthetic records, never real firmware."""
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from gpu_ldr_inspect import apple15_skips_zero, inspect, summarize_ranges


def fixture():
    data = bytearray(256)
    struct.pack_into("<I", data, 8, 16)
    struct.pack_into("<HHIII", data, 16, 0, 20, 36, 0x1000, 128)
    struct.pack_into("<HHII", data, 36, 4, 16, 52, 0x2000)
    struct.pack_into("<I", data, 48, 8)
    struct.pack_into("<HHII", data, 52, 5, 16, 68, 160)
    struct.pack_into("<HHII", data, 68, 3, 16, 84, 192)
    struct.pack_into("<HHI", data, 84, 0x10, 16, 0xffffffff)
    struct.pack_into("<HH", data, 128, 0, 10)
    data[132:136] = b"test"
    struct.pack_into("<HHIII", data, 160, 0, 18, 2, 0x1234, 5)
    struct.pack_into("<HH", data, 192, 0, 22)
    struct.pack_into("<IIII", data, 196, 1, 0x2000, 0x1000, 0)
    return data


class LdrTests(unittest.TestCase):
    def test_valid_image(self):
        counts, copied, zeroed, config, threads = inspect(fixture())
        self.assertEqual(counts, {"load": 1, "zero": 1, "config": 1, "start": 1, "comment": 1})
        self.assertEqual((copied, zeroed, config, threads), (4, 8, 1, 1))
        self.assertEqual(summarize_ranges(fixture()), (2, False, 1, 1, 1, 0, 0, 0, 0, 0))

    def test_overlapping_ranges_disable_membership_classification(self):
        data = fixture()
        struct.pack_into("<I", data, 44, 0x1002)
        self.assertEqual(summarize_ranges(data), (2, True, 1, None, None, 0, 0, 0, None, None))

    def test_core_zero_range_crossing(self):
        data = fixture()
        struct.pack_into("<II", data, 44, 0x8000bff0, 32)
        struct.pack_into("<I", data, 200, 0x8000bff5)
        self.assertEqual(summarize_ranges(data)[-5:], (1, 1, 1, 1, 1))

    def test_ios15_guard_boundaries(self):
        self.assertFalse(apple15_skips_zero(0x8000007f))
        self.assertTrue(apple15_skips_zero(0x80000080))
        self.assertTrue(apple15_skips_zero(0x8000bfff))
        self.assertFalse(apple15_skips_zero(0x8000c000))

    def test_cycle_is_rejected(self):
        data = fixture()
        struct.pack_into("<I", data, 88, 16)
        with self.assertRaisesRegex(ValueError, "cyclic"):
            inspect(data)

    def test_record_limit(self):
        with patch("gpu_ldr_inspect.MAX_RECORDS", 2):
            with self.assertRaisesRegex(ValueError, "too many LDR records"):
                inspect(fixture())

    def test_payload_outside_image_is_rejected(self):
        data = fixture()
        struct.pack_into("<I", data, 28, 255)
        with self.assertRaisesRegex(ValueError, "outside"):
            inspect(data)

    def test_short_and_misaligned_records_are_rejected(self):
        data = fixture()
        struct.pack_into("<H", data, 18, 8)
        with self.assertRaisesRegex(ValueError, "short"):
            inspect(data)
        data = fixture()
        struct.pack_into("<H", data, 162, 17)
        with self.assertRaisesRegex(ValueError, "misaligned"):
            inspect(data)

    def test_unknown_configuration_and_address_wrap_are_rejected(self):
        data = fixture()
        struct.pack_into("<I", data, 164, 1)
        with self.assertRaisesRegex(ValueError, "unsupported configuration"):
            inspect(data)
        data = fixture()
        struct.pack_into("<I", data, 24, 0xfffffffe)
        with self.assertRaisesRegex(ValueError, "wraps"):
            inspect(data)
        data = fixture()
        struct.pack_into("<H", data, 84, 0x11)
        self.assertEqual(inspect(data)[0]["comment"], 1)
        data = fixture()
        struct.pack_into("<H", data, 84, 6)
        with self.assertRaisesRegex(ValueError, "unsupported LDR command"):
            inspect(data)

    def test_cli_span_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image"
            image.write_bytes(b"prefix" + fixture())
            command = [sys.executable, str(Path(__file__).with_name("gpu_ldr_inspect.py")), str(image)]
            result = subprocess.run(command + ["--offset", "6", "--size", "256"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("records=5", result.stdout)
            self.assertNotIn("test", result.stdout)
            result = subprocess.run(command + ["--offset", "6", "--size", "257"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid image span", result.stderr)


if __name__ == "__main__":
    unittest.main()
