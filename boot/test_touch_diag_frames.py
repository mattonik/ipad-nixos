#!/usr/bin/env python3
"""Check touch-diag.c's SPI frame constants against the capture analyzer."""
from pathlib import Path
import re
import unittest

import analyze_touch_capture as capture

SOURCE = Path(__file__).with_name("touch-diag.c").read_text()


def frame(name):
    match = re.search(rf"{name}\[\d+\] = \{{([^}}]*)\}}", SOURCE)
    assert match, name
    return bytes(int(x, 0) for x in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", match.group(1)))


class FrameTests(unittest.TestCase):
    def test_wake(self):
        data = frame("F_WAKE")
        self.assertEqual(len(data), 16)
        self.assertEqual(capture.summarize((data, None))["kind"], "n1_wake_command")

    def test_atn_short_and_long(self):
        self.assertEqual(capture.summarize((frame("F_ATN_SHORT"), None))["kind"],
                         "legacy_short_ack_query")
        self.assertEqual(capture.summarize((frame("F_ATN_LONG"), None))["kind"],
                         "legacy_long_response_query")

    def test_dummy_is_atn_followed_by_seven_filler_words(self):
        data = frame("F_DUMMY")
        self.assertEqual(data, bytes.fromhex("1aa1") + bytes.fromhex("18e1") * 7)

    def test_no_write_or_firmware_frames_in_source(self):
        for opcode in ("0x1e, 0x33", "0x1d, 0x53", "0x1c, 0x73"):
            self.assertNotIn(opcode, SOURCE)

    def test_defaults_match_the_design(self):
        self.assertIn("g_spi_mode = 3", SOURCE)
        self.assertIn("g_spi_hz = 1984000", SOURCE)


if __name__ == "__main__":
    unittest.main()
