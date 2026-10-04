#!/usr/bin/env python3
"""Inspect/extract J81 touch firmware locally; never upload or infer wire fields.

The known 12B410 asset is a preconstructed Z2 packet, not Linux Z2FW.
Only its identity, metadata and outer envelope are established by the current
research. Length/address/checksum fields and boot acknowledgements remain opaque.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
from xml.parsers.expat import ExpatError


REPO = Path(__file__).resolve().parent.parent
PERSONALITY = "C1F15,2"
PAYLOAD_SIZE = 59288
PAYLOAD_SHA256 = "9948ce32f7ec68507d58a01392fc2ac8add5bfeace4c88310da2107b1e2d54e2"
MAX_SOURCE_BYTES = 1024 * 1024
UNKNOWN_FIELDS = [
    "internal packet layout and checksums",
    "bootloader acknowledgement format and success predicate",
    "calibration envelope",
]


class InspectionError(ValueError):
    """The local asset failed an evidence-backed validation."""


def sha256_argument(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise argparse.ArgumentTypeError("SHA-256 must be exactly 64 hexadecimal digits")
    return value.lower()


def read_bounded(path: Path) -> bytes:
    if not path.is_file():
        raise InspectionError("source must be a regular file")
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InspectionError("source must be a regular file")
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if not data:
        raise InspectionError("source is empty")
    if len(data) > MAX_SOURCE_BYTES:
        raise InspectionError("source exceeds the 1 MiB inspection limit")
    return data


def inspect(data: bytes, source_format: str, expected_sha256: str) -> tuple[dict, bytes]:
    """Validate known facts only; bytes after the marker are deliberately opaque."""
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise InspectionError("source must contain 1 byte through 1 MiB")
    source_digest = hashlib.sha256(data).hexdigest()
    metadata = None
    if source_format == "mtprops":
        # Apple's normal plist DOCTYPE is allowed; custom XML entities are not.
        if b"<!ENTITY" in data.upper():
            raise InspectionError("XML entity declarations are unsupported")
        try:
            props = plistlib.loads(data)
        except (ValueError, TypeError, OverflowError, RecursionError, ExpatError) as error:
            raise InspectionError("source is not a supported property list") from error
        # Reject an unexpected board/personality instead of selecting its first entry.
        if not isinstance(props, dict) or set(props) != {PERSONALITY}:
            raise InspectionError("expected the single J81 personality C1F15,2")
        entry = props[PERSONALITY]
        if not isinstance(entry, dict):
            raise InspectionError("J81 personality must be a dictionary")
        if entry.get("PreconstructedBootloadPacketType") != "Z2":
            raise InspectionError("expected PreconstructedBootloadPacketType Z2")
        if entry.get("Constructed Firmware Version") != "0x0381.bin":
            raise InspectionError("expected constructed firmware version 0x0381.bin")
        reset = entry.get("ResetInterval")
        if type(reset) is not int or reset != 432000:
            raise InspectionError("expected integer ResetInterval 432000")
        payload = entry.get("Constructed Firmware")
        if not isinstance(payload, bytes):
            raise InspectionError("Constructed Firmware must be plist data")
        metadata = {
            "personality": PERSONALITY,
            "packet_type": "Z2",
            "version": "0x0381.bin",
            "reset_interval": reset,
        }
    elif source_format == "constructed":
        payload = data
    else:
        raise InspectionError("unsupported source format")

    if payload.startswith(b"Z2FW"):
        raise InspectionError("Linux Z2FW is not the J81 preconstructed packet")
    if len(payload) < 2:
        raise InspectionError("packet is too short for the established marker")
    if payload[:2] != b"\x18\xe1":
        raise InspectionError("expected little-endian 0xe118 marker")
    if len(payload) % 4:
        raise InspectionError("packet length must be four-byte aligned")
    if len(payload) != PAYLOAD_SIZE:
        raise InspectionError("expected the recorded 59288-byte J81 packet")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise InspectionError("constructed payload SHA-256 does not match the expected identity")

    return {
        "source_format": source_format,
        "source_sha256": source_digest,
        "payload_size": len(payload),
        "payload_sha256": digest,
        "matches_recorded_12B410_payload": digest == PAYLOAD_SHA256,
        "metadata": metadata,
        "marker": "0xe118 (little-endian)",
        "alignment": 4,
        "transport_ready": False,
        "unresolved": UNKNOWN_FIELDS.copy(),
    }, payload


def private_output(path: Path) -> Path:
    """Resolve symlinks before checking Git policy; never overwrite an output."""
    path = path.expanduser().resolve()
    try:
        relative = path.relative_to(REPO)
    except ValueError:
        relative = None
    if relative is not None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(relative)], cwd=REPO, check=False
        )
        if ignored.returncode != 0:
            raise InspectionError("an extracted asset inside the repository must be Git-ignored")
    if path.exists():
        raise InspectionError("refusing to overwrite an existing output")
    return path


def write_private(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
    except BaseException:
        path.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="local J81.mtprops or extracted constructed packet")
    parser.add_argument("--format", choices=("mtprops", "constructed"), default="mtprops")
    parser.add_argument(
        "--expected-sha256", type=sha256_argument, default=PAYLOAD_SHA256,
        help="payload identity; defaults to the recorded J81 12B410 hash",
    )
    parser.add_argument("--output", type=Path, help="optional private, exclusive extraction destination")
    parser.add_argument("--json", action="store_true", help="print metadata only, never firmware bytes")
    args = parser.parse_args(argv)
    try:
        report, payload = inspect(read_bounded(args.source.expanduser()), args.format, args.expected_sha256)
        if args.output is not None:
            if args.format != "mtprops":
                raise InspectionError("--output is only supported for mtprops extraction")
            write_private(private_output(args.output), payload)
    except (InspectionError, OSError) as error:
        # Filesystem exceptions may include private local path names. Do not echo them.
        message = str(error) if isinstance(error, InspectionError) else "local file operation failed"
        parser.exit(1, f"inspection failed: {message}\n")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"J81 envelope and expected identity verified: {report['payload_size']} bytes")
        print(f"Payload SHA-256: {report['payload_sha256']}")
        print(f"Recorded 12B410 identity: {'yes' if report['matches_recorded_12B410_payload'] else 'no (explicit override)'}")
        print("Transport ready: no; internal packet layout/checksums and boot ACK remain unresolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
