#!/usr/bin/env python3
"""Offline J81 asset tests: synthetic bytes only, no Apple firmware or USB."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

import inspect_j81_touch as inspector


PAYLOAD = b"\x18\xe1" + bytes(range(256)) * 231 + b"\0" * 150
assert len(PAYLOAD) == inspector.PAYLOAD_SIZE
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
PROPS = {
    "C1F15,2": {
        "Constructed Firmware": PAYLOAD,
        "Constructed Firmware Version": "0x0381.bin",
        "PreconstructedBootloadPacketType": "Z2",
        "ResetInterval": 432000,
    }
}


class EnvelopeTests(unittest.TestCase):
    def test_xml_and_binary_plists_extract_identically(self):
        for fmt in (plistlib.FMT_XML, plistlib.FMT_BINARY):
            with self.subTest(format=fmt):
                source = plistlib.dumps(PROPS, fmt=fmt)
                report, payload = inspector.inspect(source, "mtprops", DIGEST)
                self.assertEqual(payload, PAYLOAD)
                self.assertEqual(report["source_sha256"], hashlib.sha256(source).hexdigest())
                self.assertEqual(report["metadata"]["personality"], "C1F15,2")
                self.assertFalse(report["transport_ready"])
                self.assertFalse(report["matches_recorded_12B410_payload"])

    def test_raw_inspection_has_no_invented_metadata(self):
        report, payload = inspector.inspect(PAYLOAD, "constructed", DIGEST)
        self.assertEqual(payload, PAYLOAD)
        self.assertIsNone(report["metadata"])
        self.assertEqual(len(report["unresolved"]), 3)

    def test_default_identity_rejects_synthetic_packet(self):
        with self.assertRaisesRegex(inspector.InspectionError, "SHA-256"):
            inspector.inspect(PAYLOAD, "constructed", inspector.PAYLOAD_SHA256)

    def test_corruption_with_valid_marker_is_rejected(self):
        corrupt = PAYLOAD[:-1] + b"\x01"
        with self.assertRaisesRegex(inspector.InspectionError, "SHA-256"):
            inspector.inspect(corrupt, "constructed", DIGEST)

    def test_packet_envelope_failures(self):
        cases = [
            (b"", "1 byte"), (b"\x18", "too short"),
            (b"Z2FW" + PAYLOAD[4:], "Z2FW"),
            (b"\xe1\x18" + PAYLOAD[2:], "little-endian"),
            (PAYLOAD[:-1], "aligned"), (PAYLOAD[:-4], "59288"),
            (PAYLOAD + b"\0" * 4, "59288"),
            (b"x" * (inspector.MAX_SOURCE_BYTES + 1), "1 MiB"),
        ]
        for data, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(inspector.InspectionError, message):
                    inspector.inspect(data, "constructed", DIGEST)

    def test_missing_or_wrong_metadata(self):
        for key, bad in [
            ("Constructed Firmware", "not data"),
            ("Constructed Firmware", 59288),
            ("Constructed Firmware Version", "other.bin"),
            ("PreconstructedBootloadPacketType", "N1"),
            ("ResetInterval", True), ("ResetInterval", "432000"),
            ("ResetInterval", 432001),
        ]:
            for remove in (False, True):
                with self.subTest(key=key, remove=remove, bad=bad):
                    props = copy.deepcopy(PROPS)
                    if remove:
                        del props["C1F15,2"][key]
                    else:
                        props["C1F15,2"][key] = bad
                    with self.assertRaises(inspector.InspectionError):
                        inspector.inspect(plistlib.dumps(props), "mtprops", DIGEST)

    def test_wrong_board_or_ambiguous_personality(self):
        for props in ({}, [], {"J82": PROPS["C1F15,2"]},
                      {**PROPS, "other": {}}, {"C1F15,2": "wrong"}):
            with self.subTest(props_type=type(props)):
                with self.assertRaises(inspector.InspectionError):
                    inspector.inspect(plistlib.dumps(props), "mtprops", DIGEST)

    def test_malformed_plists_are_controlled_errors(self):
        for data in (b"not a plist", b"<?xml version='1.0'?><plist><dict>",
                     b"bplist00\0\0", b"<!ENTITY x 'bad'>"):
            with self.subTest(data=data):
                with self.assertRaises(inspector.InspectionError):
                    inspector.inspect(data, "mtprops", DIGEST)

    def test_unresolved_fields_are_not_shared_mutable_state(self):
        report, _ = inspector.inspect(PAYLOAD, "constructed", DIGEST)
        report["unresolved"].clear()
        self.assertEqual(len(inspector.UNKNOWN_FIELDS), 3)


class FileAndCommandTests(unittest.TestCase):
    def test_bounded_file_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source"
            for data in (b"", b"x" * (inspector.MAX_SOURCE_BYTES + 1)):
                path.write_bytes(data)
                with self.assertRaises(inspector.InspectionError):
                    inspector.read_bounded(path)
            path.write_bytes(b"x" * inspector.MAX_SOURCE_BYTES)
            self.assertEqual(len(inspector.read_bounded(path)), inspector.MAX_SOURCE_BYTES)
            with self.assertRaises(inspector.InspectionError):
                inspector.read_bounded(Path(directory))

    def test_private_extraction_and_metadata_only_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private-name.mtprops"
            output = Path(directory) / "touch" / "packet.bin"
            source.write_bytes(plistlib.dumps(PROPS))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = inspector.main([str(source), "--expected-sha256", DIGEST,
                                         "--output", str(output), "--json"])
            self.assertEqual(result, 0)
            self.assertEqual(output.read_bytes(), PAYLOAD)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["transport_ready"])
            self.assertNotIn("private-name", stdout.getvalue())
            self.assertNotIn(str(output), stdout.getvalue())
            with self.assertRaises(inspector.InspectionError):
                inspector.private_output(output)
            with self.assertRaises(FileExistsError):
                inspector.write_private(output, b"replacement")
            self.assertEqual(output.read_bytes(), PAYLOAD)

    def test_git_output_policy_and_symlink_resolution(self):
        # A real temporary Git repository tests tracked, ignored and escaped paths.
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("firmware/\n")
            tracked = root / "tracked.bin"
            tracked.write_bytes(b"original")
            subprocess.run(["git", "add", "tracked.bin"], cwd=root, check=True)
            (root / "firmware").mkdir()
            (root / "firmware" / "escape").symlink_to(root, target_is_directory=True)
            with patch.object(inspector, "REPO", root):
                self.assertEqual(inspector.private_output(root / "firmware/new.bin"),
                                 root / "firmware/new.bin")
                for bad in (root / "new.bin", tracked,
                            root / "firmware/escape/new.bin"):
                    with self.subTest(path=bad):
                        with self.assertRaises(inspector.InspectionError):
                            inspector.private_output(bad)

    def test_failure_never_writes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mtprops"
            source.write_bytes(plistlib.dumps(PROPS))
            output = Path(directory) / "output.bin"
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    inspector.main([str(source), "--output", str(output)])
            self.assertEqual(error.exception.code, 1)
            self.assertFalse(output.exists())

    def test_invalid_hash_is_rejected_before_reading_source(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                inspector.main(["nonexistent", "--expected-sha256", "bad"])
        self.assertEqual(error.exception.code, 2)

    def test_cli_raw_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "packet.bin"
            source.write_bytes(PAYLOAD)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(inspector.main([str(source), "--format", "constructed",
                                                "--expected-sha256", DIGEST]), 0)
            output = Path(directory) / "output.bin"
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    inspector.main([str(source), "--format", "constructed",
                                    "--expected-sha256", DIGEST, "--output", str(output)])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
