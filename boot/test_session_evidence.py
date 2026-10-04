#!/usr/bin/env python3
"""Offline evidence tests: hashing, permissions, private output and bad inputs."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from session_evidence import ROOT, SessionEvidence


class EvidenceTests(unittest.TestCase):
    def test_manifest_and_transcript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "Image"
            artifact.write_bytes(b"synthetic kernel\0")
            session = SessionEvidence([f"kernel={artifact}"], parent=root / "sessions")
            manifest_path = session.directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["artifacts"][0]["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(manifest["artifacts"][0]["bytes"], len(artifact.read_bytes()))
            self.assertEqual(len(manifest["git_commit"]), 40)
            self.assertIn("python", manifest["tools"])
            session.record(command="false", returncode=1, output="line\nnext", completion="completed")
            session.record(command="slow", returncode=None, output="partial", completion="incomplete")
            events = [json.loads(line) for line in session.transcript.read_text().splitlines()]
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["output"], "line\nnext")
            self.assertIsNone(events[1]["returncode"])
            if os.name == "posix":
                self.assertEqual(session.directory.stat().st_mode & 0o777, 0o700)
                for path in (manifest_path, session.transcript):
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_bad_inputs_create_no_session(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "sessions"
            file = Path(directory) / "file"
            file.write_bytes(b"fixture")
            for values in (["bad"], [f"={file}"], [f"same={file}", f"same={file}"], ["missing=/nonexistent/session-fixture"]):
                with self.subTest(values=values), self.assertRaises((ValueError, OSError)):
                    SessionEvidence(values, parent=parent)
                self.assertFalse(parent.exists())

    def test_default_directory_is_private_ignored_capture_path(self):
        import subprocess
        target = ROOT / "artifacts/live/sessions/example/commands.jsonl"
        self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(target)]).returncode, 0)

    def test_recording_error_surfaces_without_retry(self):
        from unittest.mock import Mock
        import ipad_console
        shell = ipad_console.IPadShell(evidence=Mock())
        shell.evidence.record.side_effect = OSError("disk full")
        with self.assertRaisesRegex(RuntimeError, "record failed.*completed.*status 7"):
            shell._record("false", "time", 0, "completed", 7, "output")
        self.assertEqual(shell.evidence.record.call_count, 1)


if __name__ == "__main__":
    unittest.main()
