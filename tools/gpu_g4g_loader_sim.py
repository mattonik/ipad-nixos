#!/usr/bin/env python3
"""Simulate Apple G4G host operations in memory; never execute firmware."""
import argparse
import json
from pathlib import Path
import struct

from gpu_ldr_inspect import host_report


def simulate(data):
    report = host_report(data)
    operations = []
    for record in report["records"]:
        kind = record["kind"]
        if kind == "load":
            operations.append({"op": "load-review", "class": record["address_class"],
                               "address": record["address"], "length": record["length"]})
        elif kind == "zero":
            operations.append({"op": "skip-zero" if record["apple81_core_guard"] else "zero-review",
                               "class": record["address_class"], "address": record["address"],
                               "length": record["length"]})
        elif kind == "config":
            operations.extend({"op": "config-review", "address": write["address"],
                               "value": write["value"]} for write in record["writes"])
        elif kind == "start":
            operations.append({"op": "thread-review", "entries": len(record["threads"])})
    return {
        "execution_allowed": False,
        "firmware_bytes_copied": False,
        "mmio_operations": 0,
        "operations": operations,
        "summary": {
            "load_reviews": sum(op["op"] == "load-review" for op in operations),
            "zero_reviews": sum(op["op"] == "zero-review" for op in operations),
            "skipped_zeros": sum(op["op"] == "skip-zero" for op in operations),
            "config_reviews": sum(op["op"] == "config-review" for op in operations),
            "thread_reviews": sum(op["op"] == "thread-review" for op in operations),
        },
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
        print(json.dumps(simulate(data), sort_keys=True))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid image span: {error}\n")


if __name__ == "__main__":
    main()
