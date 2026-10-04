#!/usr/bin/env python3
"""Synthetic capture tests; no private assets or device access."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_touch_capture as capture

# Legacy source builder: address 0x12345678, input 01 02 03 04, wrapper.
GOLDEN = bytes.fromhex("18e1 3001 0001 56781234 0115 02010403 000a0000")


class CaptureTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private_capture.jsonl"
            path.write_text(text)
            return capture.load_capture(path)

    def test_valid_golden_packet(self):
        result = capture.summarize((GOLDEN, None))
        self.assertEqual(result["reference_status"], "matches_legacy_layout")
        self.assertEqual(result["advertised_data_bytes"], 4)
        self.assertNotIn("address", result)

    def test_all_calibration_caller_sizes(self):
        for words in range(1, 253):
            data = bytes(range(256)) * (words // 64) + bytes(range((words % 64) * 4))
            header = bytes([0, words, 0x56, 0x78, 0x12, 0x34])
            checksum = sum(data)
            packet = (b"\x18\xe1\x30\x01" + header + sum(header).to_bytes(2, "big")
                      + data + (checksum & 65535).to_bytes(2, "big")
                      + (checksum >> 16).to_bytes(2, "big"))
            self.assertEqual(capture.summarize((packet, None))["reference_status"], "matches_legacy_layout")

    def test_truncated_extended_and_corrupt_packets(self):
        for size in range(4, len(GOLDEN)):
            self.assertNotEqual(capture.summarize((GOLDEN[:size], None)).get("reference_status"), "matches_legacy_layout")
        self.assertEqual(capture.summarize((GOLDEN + b"\x00", None))["reference_status"], "length_mismatch")
        for offset in (10, 12, 16):
            data = bytearray(GOLDEN)
            data[offset] ^= 1
            self.assertEqual(capture.summarize((bytes(data), None))["reference_status"], "checksum_mismatch")

    def test_unsupported_count_does_not_extrapolate(self):
        for high, low in ((1, 1), (0, 0), (0, 253), (0, 255)):
            data = bytearray(GOLDEN)
            data[4:6] = bytes((high, low))
            self.assertEqual(capture.summarize((bytes(data), None))["reference_status"], "outside_reviewed_count_domain")

    def test_byte_sum_cannot_prove_payload_order(self):
        changed = GOLDEN[:12] + GOLDEN[12:16][::-1] + GOLDEN[16:]
        self.assertEqual(capture.summarize((changed, None))["reference_status"], "matches_legacy_layout")
        report = capture.analyze([(changed, None)], [(GOLDEN, None)])
        self.assertFalse(report["comparison"]["pairs"][0]["tx_equal"])

    def test_ack_direction_missing_rx_and_long_query(self):
        for rx, expected in ((b"\x4b\xc1", True), (b"\xc1\x4b", False), (None, None)):
            self.assertIs(capture.summarize((capture.ACK, rx))["response_matches_legacy_4bc1"], expected)
        self.assertEqual(capture.summarize((capture.LONG_ACK, b"12345678"))["kind"], "legacy_long_response_query")
        self.assertEqual(capture.summarize((b"\x4b\xc1", capture.ACK))["kind"], "opaque")

    def test_constructed_prefix_is_not_calibration_proof(self):
        self.assertEqual(capture.summarize((b"\x18\xe1" + b"x" * 59286, None))["kind"], "opaque_18e1_prefixed_transfer")

    def test_schema_and_private_errors(self):
        invalid = ('{"tx":"SECRET", "rx":null}', '{"tx":"1aa1","rx":"00"}',
                   '{"tx":"1aa1","rx":null,"serial":"SECRET"}',
                   '{"tx":"00","tx":"1aa1","rx":null}', '["SECRET"]',
                   '{"tx":null,"rx":null}', '{"tx":"","rx":""}', 'SECRET')
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(capture.CaptureError) as raised:
                self.load(text)
            self.assertEqual(str(raised.exception), "invalid record 1")

    def test_input_bounds_and_empty_capture(self):
        for variable, limit, text in (("MAX_FILE", 1, '{"tx":"00","rx":null}'),
                                      ("MAX_LINE", 5, '{"tx":"00","rx":null}'),
                                      ("MAX_RECORDS", 1, '{"tx":"00","rx":null}\n' * 2),
                                      ("MAX_TRANSFER", 1, '{"tx":"0000","rx":null}')):
            with patch.object(capture, variable, limit), self.assertRaises(capture.CaptureError):
                self.load(text)
        with self.assertRaises(capture.CaptureError):
            self.load("")

    def test_positional_comparison_no_invented_rx(self):
        a = [(capture.ACK, None), (GOLDEN, None)]
        b = [(capture.ACK, b"\x4b\xc1")]
        result = capture.analyze(a, b)
        self.assertFalse(result["j81_protocol_validated"])
        self.assertFalse(result["comparison"]["same_transaction_count"])
        self.assertEqual(len(result["comparison"]["pairs"]), 1)
        self.assertIsNone(result["comparison"]["pairs"][0]["rx_equal"])

    def test_no_payload_or_unknown_response_in_report(self):
        secret = b"PRIVATE-CALIBRATION"
        result = json.dumps(capture.analyze([(secret, secret), (capture.LONG_ACK, b"SECRET!!")]))
        for value in (secret.decode(), secret.hex(), "SECRET", b"SECRET!!".hex()):
            self.assertNotIn(value, result)

    def test_cli_missing_path_is_not_echoed(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(SystemExit):
            capture.main(["/nonexistent/PRIVATE_SERIAL/capture.jsonl"])
        self.assertNotIn("PRIVATE_SERIAL", output.getvalue())

    def test_uppercase_and_spaces_load(self):
        self.assertEqual(self.load('{"tx":"1A A1","rx":"4B C1"}'), [(capture.ACK, b"\x4b\xc1")])


if __name__ == "__main__":
    unittest.main()
