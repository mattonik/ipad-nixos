#!/usr/bin/env python3
"""Build a non-executable review plan for an Apple G4G META image."""
import argparse
import json
from pathlib import Path
import struct

from gpu_ldr_inspect import host_report


def build_plan(data):
    """Describe host work without copying payloads or producing MMIO actions."""
    report = host_report(data)
    regions = []
    configs = []
    threads = []
    for record in report["records"]:
        kind = record["kind"]
        if kind in ("load", "zero"):
            regions.append({
                "kind": kind,
                "address": record["address"],
                "length": record["length"],
                "address_class": record["address_class"],
                "crosses_core_code_end": record["crosses_core_code_end"],
                "address_domain": "unresolved-meta-address",
                "action": "review-only",
            })
        elif kind == "config":
            configs.extend({
                "address": write["address"],
                "value": write["value"],
                "action": "review-only",
            } for write in record["writes"])
        elif kind == "start":
            threads.extend(record["threads"])
    return {
        "execution_allowed": False,
        "payload_bytes_included": False,
        "regions": regions,
        "config_writes": configs,
        "thread_records": threads,
        "requirements": report["linux_host_requirements"],
        "unresolved": [
            "Apple META-address to Linux GPU-address mapping",
            "Apple thread-start and firmware-alive handshake",
            "G4G shared-memory ABI and allocation lifetime",
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
        print(json.dumps(build_plan(data), sort_keys=True))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid image span: {error}\n")


if __name__ == "__main__":
    main()
