#!/usr/bin/env python3
"""Compare our LDR parser with the A9 extractor's private metadata JSON."""
import argparse
import json
from pathlib import Path
import struct

from gpu_ldr_inspect import MAX_IMAGE, host_report


def crosscheck(image, external):
    ours = host_report(image)["records"]
    theirs = external["records"]
    if len(ours) != len(theirs):
        raise ValueError(f"record count mismatch: {len(ours)} vs {len(theirs)}")
    for index, (left, right) in enumerate(zip(ours, theirs)):
        kind = {"start_threads": "start"}.get(right["kind"], right["kind"])
        if left["kind"] != kind:
            raise ValueError(f"record {index}: kind mismatch")
        if kind in ("load", "zero"):
            if (left["address"], left["length"]) != (right["destination"], right["size"]):
                raise ValueError(f"record {index}: range mismatch")
        elif kind == "config":
            if left["writes"] != right["writes"]:
                raise ValueError(f"record {index}: config mismatch")
        elif kind == "start":
            threads = [[t["thread"], t["sp"], t["pc"], t["catch"]]
                       for t in right["threads_inferred"]]
            if left["threads"] != threads:
                raise ValueError(f"record {index}: thread mismatch")
        elif kind != "comment":
            raise ValueError(f"record {index}: unknown kind")
    return len(ours)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args()
    try:
        if args.image.stat().st_size > MAX_IMAGE:
            raise ValueError("image too large")
        image = args.image.read_bytes()
        metadata = json.loads(args.metadata.read_text())
        count = crosscheck(image, metadata)
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        parser.exit(1, f"cross-check failed: {error}\n")
    print(f"PASS: {count} ordered LDR records agree (types, ranges, config and thread fields)")
    print("Payload bytes and LDR checksums were not independently verified.")


if __name__ == "__main__":
    main()
