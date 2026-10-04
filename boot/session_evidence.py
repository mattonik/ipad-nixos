"""Private host-side evidence for manual hardware sessions; no device access."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import uuid

ROOT = Path(__file__).resolve().parent.parent


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def git_value(*arguments):
    return subprocess.check_output(["git", "-C", str(ROOT), *arguments], text=True).strip()


class SessionEvidence:
    def __init__(self, artifacts=(), *, parent=None):
        # Hash first: bad inputs must fail before connecting to hardware.
        components = []
        names = set()
        for specification in artifacts:
            name, separator, filename = specification.partition("=")
            if not separator or not name or name in names:
                raise ValueError("artifacts require unique NAME=FILE entries")
            names.add(name)
            path = Path(filename).expanduser().resolve(strict=True)
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
            components.append(dict(name=name, path=str(path), bytes=size, sha256=digest.hexdigest()))
        commit = git_value("rev-parse", "HEAD")
        dirty = bool(git_value("status", "--porcelain"))
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex
        parent = Path(parent) if parent is not None else ROOT / "artifacts/live/sessions"
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = parent / identifier
        self.directory.mkdir(mode=0o700)
        self.transcript = self.directory / "commands.jsonl"
        manifest = dict(schema_version=1, session_id=identifier, started_utc=utc_now(),
                        git_commit=commit, git_branch=git_value("rev-parse", "--abbrev-ref", "HEAD"),
                        working_tree_dirty=dirty,
                        tools=dict(python=platform.python_version(), git=git_value("--version")),
                        host=dict(system=platform.system(), machine=platform.machine()),
                        artifacts=components,
                        scope="Host command evidence; does not prove the running device's payload identity")
        with self._new_file(self.directory / "manifest.json") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
        with self._new_file(self.transcript):
            pass

    @staticmethod
    def _new_file(path):
        return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w")

    def record(self, **event):
        with self.transcript.open("a") as stream:
            stream.write(json.dumps(dict(recorded_utc=utc_now(), **event)) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
