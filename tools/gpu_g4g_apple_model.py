#!/usr/bin/env python3
"""Model Apple G4G region ownership without allocating or executing memory."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import struct

from gpu_ldr_inspect import host_report


def build_model(data):
    report = host_report(data)
    buckets = defaultdict(lambda: {"regions": 0, "bytes": 0, "min": None, "max_end": None})
    zero_actions = []
    for record in report["records"]:
        if record["kind"] not in ("load", "zero"):
            continue
        bucket = buckets[record["address_class"]]
        start, end = record["address"], record["address"] + record["length"]
        bucket["regions"] += 1
        bucket["bytes"] += record["length"]
        bucket["min"] = start if bucket["min"] is None else min(bucket["min"], start)
        bucket["max_end"] = end if bucket["max_end"] is None else max(bucket["max_end"], end)
        if record["kind"] == "zero":
            zero_actions.append({"address": start, "length": record["length"],
                                 "action": "skip" if record["apple81_core_guard"] else "zero"})
    return {
        "execution_allowed": False,
        "payload_bytes_included": False,
        "buckets": dict(sorted(buckets.items())),
        "zero_actions": zero_actions,
        "thread_records": [r["threads"] for r in report["records"] if r["kind"] == "start"],
        "config_write_count": report["config_writes"],
        "unresolved": [
            "physical allocation backing each META bucket",
            "Apple shared-memory address translation",
            "firmware-alive and thread-start ownership",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--size", type=lambda value: int(value, 0))
    args = parser.parse_args()
    try:
        with args.image.open("rb") as stream:
            total = stream.seek(0, 2)
            size = total - args.offset if args.size is None else args.size
            if args.offset < 0 or size < 16 or args.offset + size > total:
                raise ValueError("invalid image span")
            stream.seek(args.offset)
            data = stream.read(size)
            if len(data) != size:
                raise ValueError("short image read")
        print(json.dumps(build_model(data), sort_keys=True))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid image span: {error}\n")


if __name__ == "__main__":
    main()
