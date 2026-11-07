#!/usr/bin/env python3
"""Execution-disabled model of Apple's J81 GFX clock-state ordering."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
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
    if len(writes) != 66:
        raise ValueError("Apple GFX plan must contain exactly 66 pairs")
    by_selector = {selector: [w for w in writes if w.get("selector") == selector]
                   for selector in (9, 10)}
    if any(len(entries) != 33 for entries in by_selector.values()):
        raise ValueError("Apple GFX selectors must contain 33 pairs each")
    addresses = []
    for selector, entries in by_selector.items():
        expected_base = BRIDGE_BASES[selector]
        table = bytearray()
        for entry, write in enumerate(entries):
            if write.get("entry") != entry:
                raise ValueError(f"selector {selector}: non-contiguous entry")
            offset = int(write["offset"], 16)
            address = int(write["address"], 16)
            if offset & 3 or not 0 <= offset < 0x81000:
                raise ValueError(f"selector {selector}: invalid offset")
            if address != expected_base + offset:
                raise ValueError(f"selector {selector}: address mapping mismatch")
            try:
                table.extend(struct.pack("<II", offset, int(write["value"], 16)))
            except (KeyError, TypeError, ValueError, struct.error) as error:
                raise ValueError(f"selector {selector}: invalid table value") from error
            addresses.append(address)
        if hashlib.sha256(table).hexdigest() != EXPECTED_TABLE_SHA256:
            raise ValueError(f"selector {selector}: table digest mismatch")
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
            {"kind": "provider-busy-transition", "enable": True},
            {"kind": "gpc-setup-and-poll", "required_state": 1},
        ]
    else:
        actions = [
            {"kind": "provider-busy-transition", "enable": False},
            {"kind": "flush-power-state", "index": RECORD.power_state_index},
            {"kind": "pmgr-state", "state": 0},
        ]
    return {"enable": enable, "record": RECORD.__dict__, "actions": actions}


def model_soc_busy_transition(*, enable: bool, busy_refs: int,
                              runtime_mode: bool | None,
                              setup_enabled: bool | None,
                              display_resolved: bool | None,
                              display_result: int | None,
                              current_mcc_mode: int | None,
                              busy_mcc_mode: int | None,
                              fb_mcc_mode: int = 4) -> dict:
    """Model Apple's conditional 8.1 display/cache action; never touches MMIO.

    `display_result` is 0 for success, nonzero for failure, or None if unknown.
    None MCC modes preserve the source's unresolved comparison.
    """
    if busy_refs < 0 or (not enable and busy_refs == 0):
        raise ValueError("invalid SoC-busy reference count")
    after = busy_refs + (1 if enable else -1)
    result = {"busy_refs_before": busy_refs, "busy_refs_after": after,
              "actions": []}
    edge = (enable and busy_refs == 0) or (not enable and busy_refs == 1)
    gates = (runtime_mode, setup_enabled, display_resolved)
    taken = False if not edge or False in gates else (
        None if None in gates else True)
    if not taken:
        result["actions"].append({"kind": "display-cache", "taken": taken,
                                  "gates": gates, "edge": edge})
        return result

    state = 0 if enable else 1
    desired = busy_mcc_mode if enable else fb_mcc_mode
    actions = result["actions"]
    actions.extend([
        {"kind": "pmgr-event", "event": "0x2700c001", "cache_id": 0x75,
         "state": state},
        {"kind": "display-idle-call", "state": state,
         "result": display_result},
    ])
    if display_result in (None, 0):
        call = (None if display_result is None or desired is None or
                current_mcc_mode is None else desired != current_mcc_mode)
        actions.append({"kind": "mcc-control-call", "mode": desired,
                        "called": call,
                        "effect": "unknown: guarded by Apple +0x958 and +0x978"})
        if display_result == 0:
            actions.append({"kind": "provider-cache-state-update",
                            "cache_id": 0x75, "state": state})
    actions.append({"kind": "pmgr-event", "event": "0x2700c002",
                    "cache_id": 0x75, "result": display_result})
    return result


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
