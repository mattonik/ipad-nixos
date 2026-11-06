from gpu_apple_clock_model import model


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
print("PASS: Apple J81 GFX clock-state model ordering")
