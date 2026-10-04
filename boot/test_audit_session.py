#!/usr/bin/env python3
"""Synthetic local evidence checks; no iPad, network or private captures needed."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import audit_session
from session_evidence import SessionEvidence


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.artifact = self.root / "Image"
        self.artifact.write_bytes(b"synthetic payload")
        self.session = SessionEvidence([f"kernel={self.artifact}"], parent=self.root / "sessions")
        self.event = dict(started_utc="2026-10-04T10:00:00+00:00", duration_seconds=1.5,
                          command="PRIVATE COMMAND", output="PRIVATE OUTPUT", host="PRIVATE HOST",
                          port=23, error=None, completion="completed", returncode=0)

    def record(self, **changes):
        self.session.record(**dict(self.event, **changes))

    def audit(self, artifacts=()):
        return audit_session.audit(self.session.directory, artifacts)

    def test_real_writer_and_outcome_classification(self):
        self.record()
        self.record(returncode=1)
        self.record(completion="incomplete", returncode=None, error="PRIVATE ERROR")
        result = self.audit([f"kernel={self.artifact}"])
        self.assertTrue(result["evidence_valid"])
        self.assertEqual([result[key] for key in ("records", "completed_zero", "completed_nonzero", "incomplete", "artifacts_checked")], [3, 1, 1, 1, 1])
        serialized = json.dumps(result)
        for private in ("PRIVATE", str(self.root), self.session.directory.name, "kernel"):
            self.assertNotIn(private, serialized)

    def test_empty_session_is_valid_not_successful_hardware(self):
        result = self.audit()
        self.assertTrue(result["evidence_valid"])
        self.assertEqual(result["records"], 0)
        self.assertIn("no hardware verdict", result["scope"])

    def test_unknown_completion_and_invalid_statuses(self):
        for changes in ({"completion": "passed"}, {"returncode": True}, {"returncode": 256},
                        {"completion": "incomplete"}, {"returncode": None}):
            with self.subTest(changes=changes):
                self.session.transcript.write_text("")
                self.record(**changes)
                result = self.audit()
                self.assertFalse(result["evidence_valid"])
                self.assertEqual(result["issues"][0]["code"], "completion_status_inconsistent")

    def test_partial_final_record_and_missing_newline(self):
        self.record()
        with self.session.transcript.open("ab") as stream:
            stream.write(b'{"command": "unfinished')
        result = self.audit()
        self.assertFalse(result["evidence_valid"])
        self.assertEqual(result["completed_zero"], 1)
        self.assertEqual({issue["code"] for issue in result["issues"]}, {"record_missing_newline", "record_invalid_json"})
        self.assertTrue(all(issue["record"] == 2 for issue in result["issues"]))

    def test_duplicate_keys_nonfinite_and_bad_schema(self):
        for raw in (b'{"completion":1,"completion":2}\n', b'{"duration_seconds":NaN}\n', b'[]\n', b'{}\n', b'\xff\n'):
            with self.subTest(raw=raw):
                self.session.transcript.write_bytes(raw)
                self.assertFalse(self.audit()["evidence_valid"])
        self.session.transcript.write_text("")
        self.record(duration_seconds=float("inf"))
        self.assertFalse(self.audit()["evidence_valid"])

    def test_size_limits_and_missing_files(self):
        self.session.transcript.write_bytes(b"x" * 17)
        with patch.object(audit_session, "MAX_RECORD", 16):
            self.assertEqual(self.audit()["issues"][0]["code"], "record_too_large")
        with patch.object(audit_session, "MAX_MANIFEST", 16):
            self.assertFalse(self.audit()["evidence_valid"])
        self.session.transcript.unlink()
        self.assertIn("transcript_unreadable", [item["code"] for item in self.audit()["issues"]])

    def test_manifest_metadata_and_explicit_artifact_verification(self):
        # No original file is needed unless verification is explicitly requested.
        relocated = self.root / "relocated"
        self.artifact.rename(relocated)
        self.assertTrue(self.audit()["evidence_valid"])
        self.assertTrue(self.audit([f"kernel={relocated}"])["evidence_valid"])
        relocated.write_bytes(b"modified")
        self.assertEqual(self.audit([f"kernel={relocated}"])["issues"][0]["code"], "artifact_content_mismatch")
        for argument in (f"kernel={self.artifact}", f"unknown={relocated}", "bad"):
            self.assertFalse(self.audit([argument])["evidence_valid"])
        manifest_path = self.session.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"].append(manifest["artifacts"][0])
        manifest_path.write_text(json.dumps(manifest))
        self.assertFalse(self.audit()["evidence_valid"])
        manifest_path.write_text('{"schema_version":99}')
        self.assertFalse(self.audit()["evidence_valid"])

    def test_cli_exit_and_no_private_error_details(self):
        script = Path(audit_session.__file__)
        self.record(returncode=1)
        result = subprocess.run([sys.executable, str(script), str(self.session.directory)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["completed_nonzero"], 1)
        result = subprocess.run([sys.executable, str(script), str(self.root / "PRIVATE MISSING")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PRIVATE", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
