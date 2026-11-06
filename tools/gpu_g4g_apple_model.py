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
    segments = defaultdict(lambda: {"regions": 0, "bytes": 0})
    zero_actions = []
    thread_records = [r["threads"] for r in report["records"] if r["kind"] == "start"]
    thread_stack_candidates = [
        {"thread_id": thread_id, "address": third}
        for group in thread_records
        for thread_id, second, third, flags in group
    ]
    for record in report["records"]:
        if record["kind"] not in ("load", "zero"):
            continue
        bucket = buckets[record["address_class"]]
        start, end = record["address"], record["address"] + record["length"]
        bucket["regions"] += 1
        bucket["bytes"] += record["length"]
        bucket["min"] = start if bucket["min"] is None else min(bucket["min"], start)
        bucket["max_end"] = end if bucket["max_end"] is None else max(bucket["max_end"], end)
        if record["apple_segment_index"] is not None:
            segment = segments[str(record["apple_segment_index"])]
            segment["regions"] += 1
            segment["bytes"] += record["length"]
        if record["kind"] == "zero":
            zero_actions.append({"address": start, "length": record["length"],
                                 "action": "skip" if record["apple81_core_guard"] else "zero"})
    extents = {}
    for record in report["records"]:
        slot = record.get("apple_segment_index")
        if slot is None or record["kind"] not in ("load", "zero"):
            continue
        start = record["address"] & 0x7fffffff
        end = start + record["length"]
        extent = extents.setdefault(str(slot), {"min": start, "max_end": end,
                                                "raw_bytes": 0, "regions": 0})
        extent["min"] = min(extent["min"], start)
        extent["max_end"] = max(extent["max_end"], end)
        extent["raw_bytes"] += record["length"]
        extent["regions"] += 1
    packed_offset = 0
    for slot in sorted(extents, key=int):
        extent = extents[slot]
        extent["raw_span"] = extent["max_end"] - extent["min"]
        extent["aligned_span_4k"] = (extent["raw_span"] + 0xfff) & ~0xfff
        extent["packed_offset_4k"] = packed_offset
        packed_offset += extent["aligned_span_4k"]
    for candidate in thread_stack_candidates:
        address = candidate["address"] & 0x7fffffff
        candidate["normalized_address"] = address
        candidate["segment"] = next((slot for slot, extent in extents.items()
                                      if extent["min"] <= address < extent["max_end"]), None)
        if candidate["segment"] is not None:
            extent = extents[candidate["segment"]]
            candidate["packed_offset"] = (extent["packed_offset_4k"] +
                                           address - extent["min"])
    core_loads = [r for r in report["records"]
                  if r["kind"] == "load" and r["address_class"] == "core-code"
                  and r["address"] < 0x8000c000]
    core_zeros = [r for r in report["records"]
                  if r["kind"] == "zero" and r["address_class"] == "core-code"
                  and r["apple81_core_guard"]]
    return {
        "execution_allowed": False,
        "payload_bytes_included": False,
        "buckets": dict(sorted(buckets.items())),
        "apple_segments": dict(sorted(segments.items())),
        "apple_segment_extents": dict(sorted(extents.items())),
        "apple_core_code_accounting": {
            "load_bytes": sum(r["length"] for r in core_loads),
            "skipped_zero_bytes": sum(r["length"] for r in core_zeros),
            "loader_rule": "count load records below 0x8000c000; skip guarded zero records",
        },
        "zero_actions": zero_actions,
        "thread_records": thread_records,
        "thread_stack_candidates": thread_stack_candidates,
        "config_write_count": report["config_writes"],
        "linux_mapping_candidates": {
            "core-code": {"type": "FW_COREMEM_CODE", "confidence": "candidate"},
            "core-data": {"type": "FW_COREMEM_DATA", "confidence": "candidate"},
            "global-alias": {"type": None, "confidence": "unresolved", "reason": "alias may target code or data"},
            "local/global-low": {"type": None, "confidence": "unresolved", "reason": "Apple segment ownership is not recovered"},
        },
        "apple_segment_mapping": {
            "0": {"linux_object": "FW_DATA", "confidence": "strong", "reason": "starts at 0x10000000"},
            "1": {"linux_object": "FW_DATA (second layout entry candidate)", "confidence": "tentative", "reason": "thread 1 third word points at 0x20000000; Linux can pack multiple FW_DATA entries into one allocation"},
            "2": {"linux_object": "META_BOOTLOADER", "confidence": "strong", "reason": "starts at 0xc0000000"},
            "3": {"linux_object": "FW_DATA (uncached alias)", "confidence": "strong", "reason": "0xe0000000 masks to 0x60000000, Linux data cache alias"},
        },
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
