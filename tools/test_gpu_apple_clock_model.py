from gpu_apple_clock_model import model, validate_bridge_plan


on = model(True)
assert on["record"] == {
    "device_id": 0x7C,
    "power_state_index": 100,
    "special_flags": 0x06,
    "selectors": (9, 10),
}
assert [a["kind"] for a in on["actions"]] == [
    "pmgr-state", "flush-power-state", "special-action", "special-action",
    "gpc-setup-and-poll",
]
assert [a.get("selector") for a in on["actions"] if "selector" in a] == [9, 10]

off = model(False)
assert [a.get("selector") for a in off["actions"] if "selector" in a] == [10, 9]
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
assert validate_bridge_plan(plan)["addresses"] == 66
print("PASS: Apple J81 GFX clock-state model ordering")
