from gpu_apple_clock_model import (find_gfx_record, model,
                                  model_soc_busy_transition,
                                  validate_bridge_plan)
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

gated = model_soc_busy_transition(
    enable=True, busy_refs=0, runtime_mode=False, setup_enabled=True,
    display_resolved=True, display_result=0, current_mcc_mode=4,
    busy_mcc_mode=3)
assert gated["busy_refs_after"] == 1
assert gated["actions"] == [{"kind": "display-cache", "taken": False,
                              "gates": (False, True, True), "edge": True}]

gate_unknown = model_soc_busy_transition(
    enable=True, busy_refs=0, runtime_mode=None, setup_enabled=True,
    display_resolved=True, display_result=0, current_mcc_mode=4,
    busy_mcc_mode=3)
assert gate_unknown["actions"][0]["taken"] is None

busy = model_soc_busy_transition(
    enable=True, busy_refs=0, runtime_mode=True, setup_enabled=True,
    display_resolved=True, display_result=0, current_mcc_mode=4,
    busy_mcc_mode=3)
assert [action["kind"] for action in busy["actions"]] == [
    "pmgr-event", "display-idle-call", "mcc-control-call",
    "provider-cache-state-update", "pmgr-event"]
assert busy["actions"][2]["called"] is True

unchanged = model_soc_busy_transition(
    enable=False, busy_refs=1, runtime_mode=True, setup_enabled=True,
    display_resolved=True, display_result=0, current_mcc_mode=4,
    busy_mcc_mode=3)
assert unchanged["actions"][2]["called"] is False

unknown = model_soc_busy_transition(
    enable=True, busy_refs=0, runtime_mode=True, setup_enabled=True,
    display_resolved=True, display_result=None, current_mcc_mode=None,
    busy_mcc_mode=None)
assert unknown["actions"][2]["called"] is None
assert unknown["actions"][-1]["event"] == "0x2700c002"
try:
    model_soc_busy_transition(
        enable=False, busy_refs=0, runtime_mode=True, setup_enabled=True,
        display_resolved=True, display_result=0, current_mcc_mode=4,
        busy_mcc_mode=3)
    raise AssertionError("unbalanced busy release accepted")
except ValueError:
    pass
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
