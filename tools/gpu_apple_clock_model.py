#!/usr/bin/env python3
"""Execution-disabled model of Apple's J81 GFX clock-state ordering."""

from dataclasses import dataclass
import json
from pathlib import Path
import sys


@dataclass(frozen=True)
class GfxClockRecord:
    device_id: int = 0x7C
    power_state_index: int = 100
    special_flags: int = 0x06
    selectors: tuple[int, int] = (9, 10)


RECORD = GfxClockRecord()
BRIDGE_BASES = {9: 0x201F00000, 10: 0x201F80000}
EXPECTED_TABLE_SHA256 = "b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4"


def decode_gfx_record(record: bytes) -> dict:
    """Decode one ApplePMGR 44-byte device-clocks record; no MMIO."""
    if len(record) != 44 or record[28:32] != b"GFX\0":
        raise ValueError("not a J81 GFX clock record")
    if record[3] != RECORD.device_id or record[4] != RECORD.special_flags:
        raise ValueError("unexpected GFX clock identity")
    if tuple(record[5:7]) != RECORD.selectors:
        raise ValueError("unexpected GFX bridge selectors")
    return {"device_id": record[3], "special_flags": record[4],
            "selectors": tuple(record[5:7]),
            "dependencies": tuple(record[8:12]),
            "power_state_indices": tuple(record[12:16]),
            "name": "GFX"}


def find_gfx_record(tree: dict) -> dict:
    """Find and decode the unique PMGR GFX record in a decoded iOS DT."""
    found = []
    def walk(value):
        if isinstance(value, dict):
            if "device-clocks" in value and isinstance(value["device-clocks"], str):
                import base64
                raw = base64.b64decode(value["device-clocks"], validate=True)
                if len(raw) % 44:
                    raise ValueError("invalid device-clocks length")
                for off in range(0, len(raw), 44):
                    if raw[off + 28:off + 32] == b"GFX\0":
                        found.append((off // 44, decode_gfx_record(raw[off:off + 44])))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(tree)
    if len(found) != 1:
        raise ValueError("GFX clock record absent or ambiguous")
    index, result = found[0]
    result["record_index"] = index
    if result["power_state_indices"] != (100, 0, 0, 0):
        raise ValueError("unexpected GFX power-state index")
    return result


def validate_bridge_plan(plan: dict) -> dict:
    """Validate the recovered tables without treating them as executable."""
    if plan.get("bridge_index") != 2 or plan.get("selectors") != [9, 10]:
        raise ValueError("unexpected Apple GFX bridge metadata")
    if plan.get("table_sha256") != EXPECTED_TABLE_SHA256:
        raise ValueError("unexpected Apple GFX table digest")
    writes = plan.get("writes", [])
    by_selector = {selector: [w for w in writes if w.get("selector") == selector]
                   for selector in (9, 10)}
    if any(len(entries) != 33 for entries in by_selector.values()):
        raise ValueError("Apple GFX selectors must contain 33 pairs each")
    addresses = []
    for selector, entries in by_selector.items():
        expected_base = BRIDGE_BASES[selector]
        for entry, write in enumerate(entries):
            if write.get("entry") != entry:
                raise ValueError(f"selector {selector}: non-contiguous entry")
            offset = int(write["offset"], 16)
            address = int(write["address"], 16)
            if offset & 3 or not 0 <= offset < 0x81000:
                raise ValueError(f"selector {selector}: invalid offset")
            if address != expected_base + offset:
                raise ValueError(f"selector {selector}: address mapping mismatch")
            addresses.append(address)
    if len(set(addresses)) != len(addresses):
        raise ValueError("Apple GFX bridge addresses overlap")
    return {"selectors": {str(k): len(v) for k, v in by_selector.items()},
            "addresses": len(addresses), "table_sha256": plan["table_sha256"]}


def model(enable: bool, *, clock_ref: int = 1) -> dict:
    """Return the ordered abstract actions; never emits MMIO writes."""
    if clock_ref < 0:
        raise ValueError("clock_ref must be non-negative")
    if clock_ref == 0:
        return {"enable": enable, "record": RECORD.__dict__, "actions": [],
                "blocked": "no-clock-reference"}
    if enable:
        actions = [
            {"kind": "pmgr-state", "state": 0xF},
            {"kind": "flush-power-state", "index": RECORD.power_state_index},
            {"kind": "special-action", "selector": RECORD.selectors[0]},
            {"kind": "special-action", "selector": RECORD.selectors[1]},
            {"kind": "gpc-setup-and-poll", "required_state": 1},
        ]
    else:
        actions = [
            {"kind": "special-action", "selector": RECORD.selectors[1]},
            {"kind": "special-action", "selector": RECORD.selectors[0]},
            {"kind": "flush-power-state", "index": RECORD.power_state_index},
            {"kind": "pmgr-state", "state": 0},
        ]
    return {"enable": enable, "record": RECORD.__dict__, "actions": actions}


def main() -> int:
    enable = "--disable" not in sys.argv[1:]
    plan_arg = next((arg for arg in sys.argv[1:] if arg.startswith("--plan=")), None)
    output = model(enable)
    if plan_arg:
        plan = json.loads(Path(plan_arg.split("=", 1)[1]).read_text())
        output["bridge_plan_validation"] = validate_bridge_plan(plan)
    tree_arg = next((arg for arg in sys.argv[1:] if arg.startswith("--tree=")), None)
    if tree_arg:
        output["decoded_tree_record"] = find_gfx_record(
            json.loads(Path(tree_arg.split("=", 1)[1]).read_text()))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
