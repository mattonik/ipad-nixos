#!/usr/bin/env python3
"""Reproduce a public, pinned J82 audio/sensor topology audit (not J81 data)."""

import argparse
import hashlib
import json
from pathlib import Path
import re

SOURCE_SHA256 = "ee3a9ac310203254e02f6257d1d2ba9e63b3f47e7144855071a2c9636843f15a"
PIN = "768d800c46140c9ba39a372d097fa49f7197a66d"
ROOT = "/device-tree/arm-io"
SELECTED = {
    ROOT,
    *(ROOT + "/" + name for name in (
        "uart8", "uart8/oscar", "spi1", "spi1/audio-codec",
        "i2c1", "i2c1/audio-speaker0", "i2c1/audio-speaker1",
        "i2c2", "i2c2/als1", "i2c2/als2", "i2s-switch",
        "mca0", "mca0/audio-codec", "mca1", "mca1/audio-codec-voice",
        "mca3", "mca3/audio-speaker0", "mca4", "mca4/audio-bluetooth")),
}
# No arbitrary properties, calibration, device identifiers, firmware bytes or
# audio tuning data are emitted. Input must be this exact public source.
FIELDS = {"compatible", "reg", "ranges", "interrupts", "interrupt-parent",
          "clock-gates", "dma-parent", "#address-cells", "#address-cels",
          "#size-cells", "mca-version", "oscar-version"}


def extract(text):
    stack = {}
    selected = {}
    for block in re.split(r"^-{20,}\n", text, flags=re.M):
        match = re.search(r"^( *)name +([^\n]+)", block, re.M)
        if not match:
            continue
        depth = len(match[1])
        stack = {key: val for key, val in stack.items() if key < depth}
        stack[depth] = match[2].strip()
        path = "/" + "/".join(stack.values())
        if path not in SELECTED:
            continue
        if path in selected:
            raise ValueError("duplicate selected node")
        properties = {}
        key = None
        for line in block.splitlines():
            entry = re.match(r"^ {" + str(depth) + r"}(\S+) +(.+)$", line)
            if entry:
                key, value = entry.groups()
                if key in FIELDS:
                    if key in properties:
                        raise ValueError("duplicate selected property")
                    properties[key] = value.split("|")[0].strip()
            elif key in FIELDS and "|" in line:
                properties[key] += " " + line.split("|")[0].strip()
        normalized = {}
        for key, value in properties.items():
            if re.fullmatch(r"(?:[0-9a-f]{2}\s*)+", value):
                data = bytes.fromhex(value)
                if key == "compatible":
                    normalized[key] = data.rstrip(b"\0").decode("ascii").split("\0")
                else:
                    if len(data) % 4:
                        raise ValueError("resource is not a whole number of 32-bit cells")
                    normalized[key + "_le32"] = [
                        f"0x{int.from_bytes(data[i:i+4], 'little'):x}"
                        for i in range(0, len(data), 4)]
            elif key == "compatible":
                normalized[key] = [value]
            elif re.fullmatch(r"0x[0-9a-f]+", value):
                normalized[key + "_le32"] = [hex(int(value, 16))]
            else:
                raise ValueError("unsupported selected property encoding")
        selected[path] = normalized
    if selected.keys() != SELECTED:
        raise ValueError("selected node set differs from reviewed topology")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="SoMainline/adt_collection a8/J82.adt at the documented pin")
    args = parser.parse_args()
    try:
        with args.source.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
            parser.error("source differs from the reviewed public J82 pin; private/J81 dumps are not accepted")
        nodes = extract(raw.decode("ascii"))
    except (OSError, UnicodeError, ValueError):
        parser.error("cannot decode the reviewed public source")
    print(json.dumps({"board": "J82 sibling reference only", "source_commit": PIN,
                      "source_sha256": SOURCE_SHA256, "nodes": nodes}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
