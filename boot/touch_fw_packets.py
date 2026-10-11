#!/usr/bin/env python3
"""Export the known J81 bootload transfers locally; never contact hardware.

The 12B410 Constructed Firmware plist value is already Apple's complete e118
transfer.  This tool deliberately copies it verbatim: it does not decode,
reframe, split, pad, or recalculate any private packet fields.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import inspect_j81_touch as inspector


DATA_ACK_QUERY = b"\x1a\xa1"


def packet_set(source: Path, expected_sha256: str) -> tuple[dict, tuple[bytes, bytes]]:
    """Return only the established firmware transfer and its ACK query."""
    report, firmware = inspector.inspect(
        inspector.read_bounded(source.expanduser()), "mtprops", expected_sha256
    )
    return report, (firmware, DATA_ACK_QUERY)


def export(output_dir: Path, packets: tuple[bytes, bytes]) -> list[dict]:
    """Write new private files only; a partial prior export is refused."""
    names = ("00-firmware-transfer.bin", "01-data-ack-query.bin")
    paths = [inspector.private_output(output_dir / name) for name in names]
    written: list[Path] = []
    try:
        for path, packet in zip(paths, packets):
            inspector.write_private(path, packet)
            written.append(path)
    except BaseException:
        for path in written:
            path.unlink()
        raise
    return [
        {"length": len(packet), "sha256": hashlib.sha256(packet).hexdigest()}
        for packet in packets
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="local J81.mtprops")
    parser.add_argument("output_dir", type=Path, help="new files are created here; it must be private/Git-ignored in the repository")
    parser.add_argument("--expected-sha256", type=inspector.sha256_argument,
                        default=inspector.PAYLOAD_SHA256)
    args = parser.parse_args(argv)
    try:
        _report, packets = packet_set(args.source, args.expected_sha256)
        metadata = export(args.output_dir, packets)
    except (inspector.InspectionError, OSError) as error:
        message = str(error) if isinstance(error, inspector.InspectionError) else "local file operation failed"
        parser.exit(1, f"packet export failed: {message}\n")
    for index, item in enumerate(metadata):
        print(f"packet {index}: {item['length']} bytes sha256={item['sha256']}")
    print("expected response after packet 1: 2 bytes sha256=" + hashlib.sha256(b"\x4b\xc1").hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
