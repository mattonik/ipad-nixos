#!/usr/bin/env python3
"""Summarize normalized SPI captures against a legacy Z2 reference, offline.

Input is JSON Lines, one complete chip-select interval per object, with tx/rx
hex strings (rx may be null if unobserved). Byte order must already be known.
No payloads, addresses, checksums, paths or unknown responses are printed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat

MAX_FILE = 16 * 1024 * 1024
MAX_LINE = 262144
MAX_RECORDS = 10000
MAX_TRANSFER = 65536
ACK = bytes.fromhex("1a a1")
LONG_ACK = bytes.fromhex("1a a1 18 e1 18 e1 18 e1")


class CaptureError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureError("duplicate JSON key")
        result[key] = value
    return result


def hex_bytes(value):
    if not isinstance(value, str):
        raise CaptureError("expected hexadecimal text")
    compact = value.replace(" ", "")
    if len(compact) % 2 or not re.fullmatch(r"[0-9a-fA-F]*", compact):
        raise CaptureError("expected an even number of hexadecimal digits with optional spaces")
    data = bytes.fromhex(compact)
    if len(data) > MAX_TRANSFER:
        raise CaptureError("transfer exceeds 65536 bytes")
    return data


def load_capture(path):
    if not path.is_file():
        raise CaptureError("capture must be a regular file")
    records = []
    total = 0
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise CaptureError("capture must be a regular file")
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            total += len(line)
            if total > MAX_FILE or len(line) > MAX_LINE or len(records) >= MAX_RECORDS:
                raise CaptureError("capture exceeds file, line or record limit")
            try:
                record = json.loads(line, object_pairs_hook=unique_object)
                if not isinstance(record, dict) or set(record) != {"tx", "rx"}:
                    raise CaptureError("each record must contain exactly tx and rx")
                tx = hex_bytes(record["tx"])
                rx = None if record["rx"] is None else hex_bytes(record["rx"])
                if not tx or (rx is not None and len(tx) != len(rx)):
                    raise CaptureError("tx must be nonempty and observed rx must have equal length")
            except (ValueError, TypeError, RecursionError) as error:
                raise CaptureError(f"invalid record {len(records) + 1}") from error
            records.append((tx, rx))
    if not records:
        raise CaptureError("capture contains no records")
    return records


def summarize(record):
    tx, rx = record
    result = {"tx_bytes": len(tx), "rx_observed": rx is not None, "kind": "opaque"}
    if tx == ACK:
        result.update(kind="legacy_short_ack_query",
                      response_matches_legacy_4bc1=None if rx is None else rx == b"\x4b\xc1")
    elif tx == LONG_ACK:
        # Long response semantics are not established for J81; suppress its value.
        result["kind"] = "legacy_long_response_query"
    elif tx.startswith(b"\x18\xe1\x30\x01"):
        result["kind"] = "legacy_calibration_candidate"
        if len(tx) < 16:
            result["reference_status"] = "truncated_header_or_checksum"
            return result
        # Reviewed callers emit only 1..252 words; do not extrapolate the
        # suspicious high count-byte shift in the original implementation.
        if tx[4] != 0 or not 1 <= tx[5] <= 252:
            result["reference_status"] = "outside_reviewed_count_domain"
            return result
        size = tx[5] * 4
        result["advertised_data_bytes"] = size
        if len(tx) != size + 16:
            result["reference_status"] = "length_mismatch"
            return result
        header_ok = int.from_bytes(tx[10:12], "big") == sum(tx[4:10])
        tail = tx[-4:]
        checksum = int.from_bytes(tail[:2], "big") | (int.from_bytes(tail[2:], "big") << 16)
        data_ok = checksum == sum(tx[12:-4])
        result.update(header_checksum_matches=header_ok, data_checksum_matches=data_ok,
                      reference_status="matches_legacy_layout" if header_ok and data_ok else "checksum_mismatch")
    elif tx.startswith(b"\x18\xe1"):
        result["kind"] = "opaque_18e1_prefixed_transfer"
    return result


def analyze(records, comparison=None):
    report = {"schema": 1, "profile": "openiboot-s5l8900-reference",
              "j81_protocol_validated": False,
              "transactions": [dict(index=i, **summarize(record)) for i, record in enumerate(records)]}
    if comparison is not None:
        # Positional only: never invent synchronization after a dropped record.
        report["comparison"] = {
            "alignment": "index_only_no_resynchronization",
            "reference_transactions": len(comparison),
            "same_transaction_count": len(records) == len(comparison),
            "pairs": [{"index": i, "tx_equal": a[0] == b[0],
                       "rx_equal": None if a[1] is None or b[1] is None else a[1] == b[1],
                       "reference_summary": summarize(b)}
                      for i, (a, b) in enumerate(zip(records, comparison))]}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--compare", type=Path, help="normalized reference capture; compare by index only")
    args = parser.parse_args(argv)
    try:
        report = analyze(load_capture(args.capture), load_capture(args.compare) if args.compare else None)
    except (CaptureError, OSError) as error:
        message = str(error) if isinstance(error, CaptureError) else "local file operation failed"
        parser.exit(1, f"capture analysis failed: {message}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
