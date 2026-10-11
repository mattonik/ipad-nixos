#!/usr/bin/env python3
"""Synthetic host checks for the J81 verbatim boot-transfer exporter."""
from __future__ import annotations

import contextlib
import hashlib
import io
from pathlib import Path
import plistlib
import tempfile
import unittest

import inspect_j81_touch as inspector
import touch_fw_packets as packets


FIRMWARE = b"\x18\xe1" + bytes(range(256)) * 231 + b"\0" * 150
assert len(FIRMWARE) == inspector.PAYLOAD_SIZE
DIGEST = hashlib.sha256(FIRMWARE).hexdigest()


class PacketExportTests(unittest.TestCase):
    def test_verbatim_firmware_and_ack_query(self):
        props = {"C1F15,2": {"Constructed Firmware": FIRMWARE,
                                "Constructed Firmware Version": "0x0381.bin",
                                "PreconstructedBootloadPacketType": "Z2",
                                "ResetInterval": 432000}}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "asset.mtprops"
            output = Path(directory) / "private"
            source.write_bytes(plistlib.dumps(props))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(packets.main([str(source), str(output), "--expected-sha256", DIGEST]), 0)
            self.assertEqual((output / "00-firmware-transfer.bin").read_bytes(), FIRMWARE)
            self.assertEqual((output / "01-data-ack-query.bin").read_bytes(), b"\x1a\xa1")
            self.assertEqual((output / "00-firmware-transfer.bin").read_bytes()[:2], b"\x18\xe1")
            self.assertEqual(hashlib.sha256(b"\x4b\xc1").hexdigest(),
                             "89fb43983c2a6aa0474fa910b4d6193e4e908887b4b507e8c792314ec93ddc56")
            self.assertEqual((output / "00-firmware-transfer.bin").stat().st_mode & 0o777, 0o600)
            self.assertNotIn("asset.mtprops", stdout.getvalue())
            self.assertNotIn(FIRMWARE.hex(), stdout.getvalue())

    def test_refuses_bad_identity_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.mtprops"
            source.write_bytes(plistlib.dumps({}))
            output = Path(directory) / "private"
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    packets.main([str(source), str(output)])
            self.assertEqual(error.exception.code, 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
