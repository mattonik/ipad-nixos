#!/usr/bin/env python3
"""Inspect a META LDR image without extracting or executing firmware."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import struct

MAX_IMAGE = 16 * 1024 * 1024
MAX_RECORDS = 65536


def apple15_skips_zero(address):
    """Evaluate the observed 15.8.8 type-4 start-address guard."""
    return (((address + 0x7fffff80) & 0xffffffff) >> 7) < 0x17f


def inspect(data):
    """Validate record and payload bounds and return counts, not firmware bytes."""
    def require(offset, length):
        if offset < 0 or length < 0 or offset > len(data) or length > len(data) - offset:
            raise ValueError("record or payload outside image")

    def u16(offset):
        require(offset, 2)
        return struct.unpack_from("<H", data, offset)[0]

    def u32(offset):
        require(offset, 4)
        return struct.unpack_from("<I", data, offset)[0]

    require(0, 16)
    position = u32(8)
    seen = set()
    counts = Counter()
    copied = zeroed = config = threads = 0
    while position != 0xffffffff:
        require(position, 8)
        if position in seen:
            raise ValueError("cyclic LDR record chain")
        # shortcut: cap record traversal; raise if a larger verified image is found.
        if len(seen) >= MAX_RECORDS:
            raise ValueError("too many LDR records")
        seen.add(position)
        command, record_length = u16(position), u16(position + 2)
        if record_length < 8:
            raise ValueError("short LDR record")
        require(position, record_length)
        kind = command & 0xf
        if command & 0x10:
            counts["comment"] += 1
        else:
            if kind not in (0, 3, 4, 5):
                raise ValueError(f"unsupported LDR command {kind}")
            if record_length < (20 if kind == 0 else 16):
                raise ValueError("short command record")
            counts[{0: "load", 3: "start", 4: "zero", 5: "config"}[kind]] += 1
            if kind == 4:
                length = u32(position + 12)
                if u32(position + 8) + length > 1 << 32:
                    raise ValueError("zero range wraps address space")
                zeroed += length
            else:
                block = u32(position + (12 if kind == 0 else 8))
                length = u16(block + 2)
                if length < 6:
                    raise ValueError("short LDR payload")
                require(block, length)
                size = length - 6
                if kind == 0:
                    if u32(position + 8) + size > 1 << 32:
                        raise ValueError("load range wraps address space")
                    copied += size
                elif kind == 3:
                    if size % 16:
                        raise ValueError("misaligned start-thread records")
                    threads += size // 16
                else:
                    if size % 12:
                        raise ValueError("misaligned configuration records")
                    for i in range(0, size, 12):
                        if u32(block + 4 + i) != 2:
                            raise ValueError("unsupported configuration command")
                    config += size // 12
        position = u32(position + 4)
    return counts, copied, zeroed, config, threads


def summarize_ranges(data):
    """Summarize destinations and thread-field membership without exposing bytes."""
    inspect(data)
    u16 = lambda offset: struct.unpack_from("<H", data, offset)[0]
    u32 = lambda offset: struct.unpack_from("<I", data, offset)[0]
    position = u32(8)
    ranges, threads = [], []
    while position != 0xffffffff:
        command = u16(position)
        kind = command & 0xf
        if not command & 0x10 and kind in (0, 4):
            address, arg = u32(position + 8), u32(position + 12)
            length = u16(arg + 2) - 6 if kind == 0 else arg
            if length:
                # shortcut: cap metadata work at 65,536 entries; raise for a larger verified image.
                if len(ranges) >= 65536:
                    raise ValueError("too many nonempty regions")
                ranges.append((address, address + length, kind))
        elif not command & 0x10 and kind == 3:
            block = u32(position + 8)
            if len(threads) + (u16(block + 2) - 6) // 16 > 65536:
                raise ValueError("too many thread entries")
            for offset in range(0, u16(block + 2) - 6, 16):
                threads.append(struct.unpack_from("<IIII", data, block + 4 + offset))
        position = u32(position + 4)
    ranges.sort()
    core_zero = sum(kind == 4 and 0x80000000 <= start < 0x8000c000
                    for start, _, kind in ranges)
    core_zero_cross = sum(kind == 4 and 0x80000000 <= start < 0x8000c000 < end
                          for start, end, kind in ranges)
    ios15_core_zero = sum(kind == 4 and apple15_skips_zero(start) for start, _, kind in ranges)
    furthest = 0
    overlapping = False
    for start, end, _ in ranges:
        if start < furthest:
            overlapping = True
        furthest = max(furthest, end)
    if overlapping:
        return (len(ranges), True, len(threads), None, None, core_zero,
                core_zero_cross, ios15_core_zero, None, None)
    starts = [item[0] for item in ranges]
    def contains(value, kind):
        index = bisect_right(starts, value) - 1
        return index >= 0 and ranges[index][2] == kind and value < ranges[index][1]
    def in_skipped_zero(value, ios15):
        index = bisect_right(starts, value) - 1
        if index < 0:
            return False
        start, end, kind = ranges[index]
        if kind != 4 or value >= end:
            return False
        return apple15_skips_zero(start) if ios15 else 0x80000000 <= start < 0x8000c000
    return (len(ranges), False, len(threads),
            sum(contains(t[1], 4) for t in threads), sum(contains(t[2], 0) for t in threads),
            core_zero, core_zero_cross, ios15_core_zero,
            sum(in_skipped_zero(t[1], False) for t in threads),
            sum(in_skipped_zero(t[1], True) for t in threads))


def host_report(data):
    """Return LDR metadata needed for an offline Apple/Linux host comparison."""
    def address_class(address):
        if 0x80000000 <= address < 0x82000000:
            return "core-code"
        if 0x82000000 <= address < 0x84000000:
            return "core-data"
        if address & 0x80000000:
            return "global-alias"
        return "local/global-low"

    inspect(data)
    u16 = lambda offset: struct.unpack_from("<H", data, offset)[0]
    u32 = lambda offset: struct.unpack_from("<I", data, offset)[0]
    records = []
    position = u32(8)
    while position != 0xffffffff:
        command = u16(position)
        kind = command & 0xf
        if command & 0x10:
            records.append({"kind": "comment"})
        elif kind == 0:
            block = u32(position + 12)
            address, length = u32(position + 8), u16(block + 2) - 6
            records.append({"kind": "load", "address": address, "length": length,
                            "address_class": address_class(address),
                            "crosses_core_code_end": address < 0x82000000 < address + length})
        elif kind == 3:
            block = u32(position + 8)
            length = u16(block + 2) - 6
            threads = [list(struct.unpack_from("<IIII", data, block + 4 + offset))
                       for offset in range(0, length, 16)]
            records.append({"kind": "start", "threads": threads})
        elif kind == 4:
            address, length = u32(position + 8), u32(position + 12)
            records.append({"kind": "zero", "address": address, "length": length,
                            "address_class": address_class(address),
                            "crosses_core_code_end": address < 0x82000000 < address + length,
                            "apple81_core_guard": 0x80000000 <= address < 0x8000c000,
                            "apple15_core_guard": apple15_skips_zero(address)})
        elif kind == 5:
            block = u32(position + 8)
            length = u16(block + 2) - 6
            writes = [
                {"address": u32(block + 4 + offset + 4),
                 "value": u32(block + 4 + offset + 8)}
                for offset in range(0, length, 12)
            ]
            records.append({"kind": "config", "writes": writes})
        position = u32(position + 4)
    loads = [r for r in records if r["kind"] == "load"]
    zeros = [r for r in records if r["kind"] == "zero"]
    return {
        "records": records,
        "load_bytes": sum(r["length"] for r in loads),
        "zero_bytes": sum(r["length"] for r in zeros),
        "config_writes": sum(len(r["writes"]) for r in records if r["kind"] == "config"),
        "thread_entries": sum(len(r.get("threads", [])) for r in records if r["kind"] == "start"),
        "linux_host_requirements": {
            "segment_setup_required": bool(loads),
            "explicit_start_thread_handling_required": any(r["kind"] == "start" for r in records),
            "zero_guard_review_required": any(r.get("apple81_core_guard") or r.get("apple15_core_guard") for r in zeros),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--offset", type=lambda x: int(x, 0), default=0)
    parser.add_argument("--size", type=lambda x: int(x, 0))
    parser.add_argument("--report", action="store_true", help="print host-layout metadata as JSON")
    args = parser.parse_args()
    try:
        with args.image.open("rb") as stream:
            total = stream.seek(0, 2)
            size = total - args.offset if args.size is None else args.size
            if args.offset < 0 or size < 16 or size > MAX_IMAGE or args.offset + size > total:
                raise ValueError("invalid image span")
            stream.seek(args.offset)
            data = stream.read(size)
            if len(data) != size:
                raise ValueError("short image read")
        counts, copied, zeroed, config, threads = inspect(data)
        (regions, overlapping, _, field1_zero, field2_load, core_zero, core_zero_cross,
         ios15_core_zero, field1_skipped_81, field1_skipped_15) = summarize_ranges(data)
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid LDR image: {error}\n")
    if args.report:
        print(json.dumps(host_report(data), sort_keys=True))
        return
    print(f"records={sum(counts.values())} load={counts['load']} zero={counts['zero']} "
          f"start={counts['start']} config={counts['config']} comment={counts['comment']}")
    print(f"load_bytes={copied} zero_bytes={zeroed} config_writes={config} thread_entries={threads}")
    print(f"nonempty_regions={regions} overlapping={str(overlapping).lower()} "
          f"thread_field1_in_zero={field1_zero} thread_field2_in_load={field2_load}")
    print(f"apple_81_core_zero_starts={core_zero} crosses_0x8000c000={core_zero_cross} "
          f"apple_15_core_zero_starts={ios15_core_zero}")
    print(f"thread_field1_in_skipped_zero_81={field1_skipped_81} "
          f"thread_field1_in_skipped_zero_15={field1_skipped_15}")


if __name__ == "__main__":
    main()
