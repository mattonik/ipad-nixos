#!/usr/bin/env python3
from gpu_g4g_allocation_model import J81_CORE_MMIO, J81_RESOURCE_REGIONS, build_model

model = build_model()
assert model["execution_allowed"] is False
assert len(model["classes"]) == 13
assert sum(item.get("registered", False) for item in model["classes"]) == 4
assert sum(item["class"] == "view-like-auxiliary" for item in model["classes"]) == 4
assert all(item["address"] == "unresolved" for item in model["classes"])
assert all(item["lifetime"][-1] == "release" for item in model["classes"])
assert len(J81_RESOURCE_REGIONS) == 4
assert all(region["selector"] == 0x90007 for region in J81_RESOURCE_REGIONS)
assert all(region["physical_base"] != J81_CORE_MMIO["physical_base"] for region in J81_RESOURCE_REGIONS)
assert J81_CORE_MMIO["physical_base"] == 0x201000000
print("PASS: J81 allocation classes and lifetimes remain execution-disabled")
