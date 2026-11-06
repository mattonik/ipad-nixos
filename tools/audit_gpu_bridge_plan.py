#!/usr/bin/env python3
"""Audit J81 bridge tables offline; never access hardware or emit table values."""
import argparse
import base64
import hashlib
import json
import re
import struct
from pathlib import Path


def child(node, name):
    matches = [entry[name] for entry in node.get("children", []) if name in entry]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} node")
    return matches[0]


def blob(value):
    if not isinstance(value, str):
        raise ValueError("expected encoded bytes")
    return base64.b64decode(value, validate=True)


def capture_table(text, name):
    pattern = re.compile(r"^\s*" + re.escape(name) + r"\s+(.+)$")
    lines = text.splitlines()
    if sum(bool(pattern.match(line)) for line in lines) != 1:
        raise ValueError(f"missing or ambiguous {name}")
    found, data = False, bytearray()
    for line in lines:
        if not found:
            match = pattern.match(line)
            if not match:
                continue
            found, field = True, match.group(1)
        else:
            if not re.match(r"^\s{30,}[0-9a-f]{2} ", line):
                break
            field = line.strip()
        data.extend(int(v, 16) for v in re.findall(r"(?<![0-9a-f])[0-9a-f]{2}(?![0-9a-f])", field.split("|")[0]))
    if not found:
        raise ValueError(f"missing {name}")
    return bytes(data)


def audit(tree, captured):
    arm = child(tree["device-tree"], "arm-io")
    pmgr = child(arm, "pmgr")
    sgx = child(arm, "sgx")
    ranges = blob(arm["ranges"])
    if len(ranges) % 24:
        raise ValueError("invalid arm-io ranges")
    translations = list(struct.iter_unpack("<QQQ", ranges))
    clocks = blob(pmgr["device-clocks"])
    if len(clocks) % 44:
        raise ValueError("invalid clock records")
    entries = [clocks[i:i+44] for i in range(0, len(clocks), 44)
               if clocks[i+28:i+32] == b"GFX\0"]
    if len(entries) != 1:
        raise ValueError("GFX record absent or ambiguous")
    gfx = entries[0]
    selectors = list(gfx[5:7])
    if gfx[3] != 0x7c or gfx[4] != 6 or selectors != [9, 10]:
        raise ValueError("unexpected GFX clock record")
    if sgx.get("clock-gates") != [0x7c] or sgx.get("power-gates") != [0x7c]:
        raise ValueError("unexpected GPU gates")
    if pmgr.get("#bridges") != 13 or pmgr.get("bridge-reg-index") != 2:
        raise ValueError("unexpected bridge mapping")
    blocks = [block for block in re.split(r"(?m)^-{5,}\s*$", captured)
              if re.search(r"(?m)^\s*compatible\s+pmgr1,t7001\s*$", block)]
    if len(blocks) != 1:
        raise ValueError("captured PMGR node absent or ambiguous")
    pmgr_capture = blocks[0]
    devices = capture_table(pmgr_capture, "devices")
    if len(devices) % 48:
        raise ValueError("invalid captured device records")
    captured_gfx = [devices[i:i+48] for i in range(0, len(devices), 48)
                    if devices[i+32:i+36] == b"GFX\0"]
    if (len(captured_gfx) != 1 or captured_gfx[0][3] != 0x7c or
            captured_gfx[0][0] != 0 or captured_gfx[0][24:26] != b"\x02\x00" or
            captured_gfx[0][28:30] != b"\x09\x0a"):
        raise ValueError("unexpected captured GFX device record")
    captured_regs = capture_table(pmgr_capture, "reg")
    if len(captured_regs) % 16:
        raise ValueError("invalid captured PMGR regions")
    regions = list(struct.iter_unpack("<QQ", captured_regs))
    all_addresses, summaries = set(), []
    for selector in selectors:
        prop = f"bridge-settings-{selector}"
        data = blob(pmgr[prop])
        if len(data) != 264 or capture_table(pmgr_capture, prop) != data:
            raise ValueError(f"{prop} length or capture mismatch")
        reg = pmgr["reg"][2 + selector]
        if regions[2 + selector] != (reg["addr"], reg["size"]):
            raise ValueError("captured PMGR region mismatch")
        matches = [(physical + reg["addr"] - child_base, reg["size"])
                   for child_base, physical, length in translations
                   if child_base <= reg["addr"] and reg["addr"] + reg["size"] <= child_base + length]
        if len(matches) != 1:
            raise ValueError("ambiguous bridge translation")
        base, size = matches[0]
        pairs = list(struct.iter_unpack("<II", data))
        offsets = [offset for offset, _ in pairs]
        if offsets != [0x18] + list(range(0x40000, 0x40080, 4)):
            raise ValueError("unexpected bridge offset order")
        for offset in offsets:
            if offset % 4 or offset + 4 > size or base + offset in all_addresses:
                raise ValueError("invalid or duplicate bridge address")
            all_addresses.add(base + offset)
        summaries.append({"selector": selector, "base": hex(base), "entries": len(pairs),
                          "sha256": hashlib.sha256(data).hexdigest()})
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="private decoded iOS 8.1 device-tree JSON")
    parser.add_argument("captured", type=Path, help="private captured J81 ADT text")
    args = parser.parse_args()
    try:
        result = audit(json.loads(args.tree.read_text()), args.captured.read_text())
    except (OSError, IndexError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"audit failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
