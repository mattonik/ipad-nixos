#!/usr/bin/env python3
"""Compare Apple G4G LDR handling with the generic Linux META policy."""
import argparse
import json
from pathlib import Path
import struct

from gpu_ldr_inspect import host_report


APPLE81_CORE_START = 0x80000000
APPLE81_CORE_END = 0x8000C000
LINUX_CORE_DATA_START = 0x82000000


def compare(data, linux_coremem_size=None):
    report = host_report(data)
    zero_diffs = []
    for record in report["records"]:
        if record["kind"] != "zero":
            continue
        address = record["address"]
        apple = "skip-core-guard" if APPLE81_CORE_START <= address < APPLE81_CORE_END else "zero"
        if linux_coremem_size is None and address < LINUX_CORE_DATA_START:
            linux = "zero-via-segment"
        elif linux_coremem_size is None:
            linux = "coremem-size-required"
        elif LINUX_CORE_DATA_START <= address < LINUX_CORE_DATA_START + linux_coremem_size:
            linux = "skip-core-data"
        else:
            linux = "zero-via-segment"
        if apple != linux:
            zero_diffs.append({"address": address, "length": record["length"],
                               "apple81": apple, "linux": linux})
    has_start = any(r["kind"] == "start" for r in report["records"])
    return {
        "apple81_zero_vs_linux": zero_diffs,
        "start_thread_difference": {
            "present": has_start,
            "apple81": "preserve-thread-record" if has_start else "none",
            "linux_generic": "constructs-boot-args-and-ignores-record" if has_start else "none",
        },
        "config_difference": {
            "writes": report["config_writes"],
            "apple81": "applies-through-META-loader",
            "linux_generic": "converts-to-boot-args",
        },
        "requires": [
            "Apple G4G allocation and address-domain mapping",
            "explicit decision for guarded core-memory zero ranges",
            "thread-start and firmware-alive handshake compatibility",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--size", type=lambda value: int(value, 0))
    parser.add_argument("--linux-coremem-size", type=lambda value: int(value, 0))
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
        print(json.dumps(compare(data, args.linux_coremem_size), sort_keys=True))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid image span: {error}\n")


if __name__ == "__main__":
    main()
