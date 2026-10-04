#!/usr/bin/env python3
"""Audit private console evidence locally; never connect to a device or replay commands."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

MAX_MANIFEST = 1024 * 1024
MAX_RECORD = 8 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except ValueError:
        return False


def audit(directory, artifacts=()):
    """Return only fixed labels, counts and record numbers, without private payloads.

    Manifest paths are metadata, never opened. Artifact verification requires
    explicit NAME=FILE arguments and does not establish running-device identity.
    """
    report = dict(schema_version=1, evidence_valid=True, records=0,
                  completed_zero=0, completed_nonzero=0, incomplete=0,
                  artifacts_checked=0, issues=[],
                  scope="Evidence structure and supplied host files only; no hardware verdict")

    def issue(code, record=None):
        report["evidence_valid"] = False
        item = dict(code=code)
        if record is not None:
            item["record"] = record
        report["issues"].append(item)

    manifest = None
    try:
        with (Path(directory) / "manifest.json").open("rb") as stream:
            raw = stream.read(MAX_MANIFEST + 1)
        if len(raw) > MAX_MANIFEST:
            issue("manifest_too_large")
        else:
            manifest = decode(raw)
    except (OSError, ValueError, UnicodeError, RecursionError):
        issue("manifest_unreadable_or_invalid_json")
    components = {}
    if not isinstance(manifest, dict):
        issue("manifest_not_object")
    else:
        valid = (type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1
                 and isinstance(manifest.get("session_id"), str) and bool(manifest["session_id"])
                 and timestamp(manifest.get("started_utc"))
                 and isinstance(manifest.get("git_commit"), str)
                 and re.fullmatch(r"[0-9a-f]{40}", manifest["git_commit"]) is not None
                 and type(manifest.get("working_tree_dirty")) is bool
                 and isinstance(manifest.get("artifacts"), list))
        if not valid:
            issue("manifest_schema_invalid")
        for component in manifest.get("artifacts", []) if isinstance(manifest.get("artifacts"), list) else []:
            if (not isinstance(component, dict) or not isinstance(component.get("name"), str)
                    or not component["name"] or component["name"] in components
                    or type(component.get("bytes")) is not int or component["bytes"] < 0
                    or not isinstance(component.get("sha256"), str)
                    or re.fullmatch(r"[0-9a-f]{64}", component["sha256"]) is None):
                issue("artifact_metadata_invalid")
                continue
            components[component["name"]] = component
    try:
        with (Path(directory) / "commands.jsonl").open("rb") as stream:
            number = 0
            while True:
                raw = stream.readline(MAX_RECORD + 1)
                if not raw:
                    break
                number += 1
                if len(raw) > MAX_RECORD:
                    issue("record_too_large", number)
                    break
                report["records"] += 1
                if not raw.endswith(b"\n"):
                    issue("record_missing_newline", number)
                try:
                    event = decode(raw)
                except (ValueError, UnicodeError, RecursionError):
                    issue("record_invalid_json", number)
                    continue
                if not isinstance(event, dict):
                    issue("record_not_object", number)
                    continue
                duration = event.get("duration_seconds")
                if (not timestamp(event.get("started_utc")) or not timestamp(event.get("recorded_utc"))
                        or type(duration) not in (int, float) or (type(duration) is float and not math.isfinite(duration)) or duration < 0
                        or not isinstance(event.get("command"), str)
                        or not isinstance(event.get("output"), str)
                        or not isinstance(event.get("host"), str)
                        or type(event.get("port")) is not int or not 1 <= event["port"] <= 65535
                        or (event.get("error") is not None and not isinstance(event["error"], str))):
                    issue("record_schema_invalid", number)
                    continue
                state, status = event.get("completion"), event.get("returncode")
                if state == "completed" and type(status) is int and 0 <= status <= 255:
                    report["completed_zero" if status == 0 else "completed_nonzero"] += 1
                elif state == "incomplete" and "returncode" in event and status is None:
                    report["incomplete"] += 1
                else:
                    issue("completion_status_inconsistent", number)
    except OSError:
        issue("transcript_unreadable")
    seen = set()
    for specification in artifacts:
        name, separator, filename = specification.partition("=")
        if not separator or not name or not filename or name in seen:
            issue("artifact_argument_invalid")
            continue
        seen.add(name)
        component = components.get(name)
        if component is None:
            issue("artifact_not_in_manifest")
            continue
        try:
            path = Path(filename).expanduser()
            if not path.is_file():
                raise OSError("not a regular file")
            digest, size = hashlib.sha256(), 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
            report["artifacts_checked"] += 1
            if digest.hexdigest() != component["sha256"] or size != component["bytes"]:
                issue("artifact_content_mismatch")
        except OSError:
            issue("artifact_unreadable")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="private session directory")
    parser.add_argument("--artifact", action="append", default=[], metavar="NAME=FILE",
                        help="verify an explicitly supplied file against recorded metadata")
    args = parser.parse_args()
    report = audit(args.directory, args.artifact)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["evidence_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
