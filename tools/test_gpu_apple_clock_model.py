from gpu_apple_clock_model import find_gfx_record, model, validate_bridge_plan
import base64
import hashlib
import struct
import gpu_apple_clock_model


on = model(True)
assert on["record"] == {
    "device_id": 0x7C,
    "power_state_index": 100,
    "special_flags": 0x06,
    "selectors": (9, 10),
}
assert [a["kind"] for a in on["actions"]] == [
    "pmgr-state", "flush-power-state", "special-action", "special-action",
    "provider-busy-transition", "gpc-setup-and-poll",
]
assert [a.get("selector") for a in on["actions"] if "selector" in a] == [9, 10]

off = model(False)
assert [a["kind"] for a in off["actions"]] == [
    "provider-busy-transition", "flush-power-state", "pmgr-state",
]
assert model(True, clock_ref=0)["blocked"] == "no-clock-reference"
plan = {
    "bridge_index": 2,
    "selectors": [9, 10],
    "table_sha256": "b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4",
    "writes": [
        {"selector": selector, "entry": entry, "offset": hex(entry * 4),
         "address": hex((0x201F00000 if selector == 9 else 0x201F80000) + entry * 4),
         "value": "0x0"}
        for selector in (9, 10) for entry in range(33)
    ],
}
digest = hashlib.sha256(b"".join(struct.pack("<II", entry * 4, 0) for entry in range(33))).hexdigest()
plan["table_sha256"] = digest
original_digest = gpu_apple_clock_model.EXPECTED_TABLE_SHA256
gpu_apple_clock_model.EXPECTED_TABLE_SHA256 = digest
assert validate_bridge_plan(plan)["addresses"] == 66
plan["writes"][0]["value"] = "0x1"
try:
    validate_bridge_plan(plan)
    raise AssertionError("modified table accepted")
except ValueError:
    pass
finally:
    gpu_apple_clock_model.EXPECTED_TABLE_SHA256 = original_digest
raw = bytearray(44)
raw[3:7] = bytes([0x7c, 0x06, 9, 10])
raw[12:16] = bytes([100, 0, 0, 0])
raw[28:32] = b"GFX\0"
tree = {"pmgr": {"device-clocks": base64.b64encode(raw).decode()}}
decoded = find_gfx_record(tree)
assert decoded["record_index"] == 0 and decoded["power_state_indices"] == (100, 0, 0, 0)
print("PASS: Apple J81 GFX clock-state model ordering")
