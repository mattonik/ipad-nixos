#!/usr/bin/env python3
"""Compare ordered GPU bridge requests against the stock board trees. Offline only."""
import argparse
import json
import re
import struct
from pathlib import Path

from audit_gpu_bridge_plan import blob, child
from audit_j81_pmgr_start import checked_file, property_at


def ordered_pairs(data):
    return list(struct.iter_unpack("<II", data))


def stock_property(tree, name):
    field = name.encode().ljust(32, b"\0")
    if tree.count(field) != 1:
        raise ValueError(f"expected one {name} property")
    return property_at(tree, tree.index(field) + 36, name.encode())


def board(directory, model, selectors):
    name = f"DeviceTree.{model}"
    arm = child(json.loads((directory / (name + ".json")).read_text())["device-tree"], "arm-io")
    pmgr = child(arm, "pmgr")
    source = (directory / (name + ".bin")).read_bytes()
    rows = []
    for selector in selectors:
        name = f"bridge-settings-{selector}"
        pairs = ordered_pairs(stock_property(source, name))
        reg = pmgr["reg"][pmgr["bridge-reg-index"] + selector]
        start, = (p + reg["addr"] - c for c, p, n in struct.iter_unpack("<QQQ", blob(arm["ranges"]))
                  if c <= reg["addr"] and reg["addr"] + reg["size"] <= c + n)
        if any(off % 4 or off + 4 > reg["size"] for off, _ in pairs):
            raise ValueError(f"{model}: pair outside bridge {selector}")
        rows.append((start, reg["size"], pairs))
    return rows


def check(extracted, packet, tree_path):
    j81, j96, n61 = [
        board(extracted / build / "devicetree", model, selectors)
        for build, model, selectors in [
            ("16G102_iPad5,3", "j81ap", (9, 10)), ("16G102_iPad5,3", "j96ap", (10, 11)),
            ("16H88_iPhone7,2", "n61ap", (10, 11))]]
    tree = checked_file(tree_path, "be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003")
    j81_pairs = [r[2] for r in j81]
    if j81_pairs != [ordered_pairs(stock_property(tree, f"bridge-settings-{n}")) for n in (9, 10)]:
        raise ValueError("19H394 and 16G102 J81 tables differ")
    data = packet / "context/data"
    hdr = [(int(a, 16), int(b, 16)) for a, b in re.findall(
        r"\{\s*(0x\w+),\s*(0x\w+)\s*\}", (data / "our-gfx-bridge-plan.h").read_text())]
    dts = (data / "n61-g4p-e074df5/t7000.dtsi").read_text()
    def cells(n):
        field, = re.findall(rf"apple,bridge{n}-settings\s*=([^;]+);", dts)
        return [int(w, 16) for w in re.findall(r"0x[\da-fA-F]+", field)]
    n61_pairs = [[tuple(cells(10))], [(4*i, v) for i, v in enumerate(cells(11))]]
    if hdr != j81_pairs[0] + j81_pairs[1] or len(hdr) != 66:
        raise ValueError("J81 header differs from stock")
    if j96 != n61 or n61_pairs != [r[2] for r in n61] or list(map(len, n61_pairs)) != [1, 32]:
        raise ValueError("N61 driver or J96 differs from N61 stock layout")
    def writes(layout):
        return {base + off: v for base, _, pairs in layout for off, v in pairs}
    a, b = writes(j81), writes(n61)
    overlap = a.keys() & b.keys()
    if overlap != {0x201f00018, 0x201f80018} or a[0x201f80018] == b[0x201f80018]:
        raise ValueError("unexpected address intersection")
    print("PASS J81: 66 ordered header entries match 19H394 and 16G102 board tables")
    print("PASS N61: 33 driver entries match 16H88 and the J96 T7000 tree in the J81 16G102 restore")
    for address in sorted(overlap):
        print(f"{address:#x}  J81={a[address]:#010x}  N61={b[address]:#010x}")
    print(f"Address counts: J81-only {len(a.keys()-b.keys())}, N61-only {len(b.keys()-a.keys())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("extracted", "packet", "j81dt"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    check(args.extracted, args.packet, args.j81dt)
