#!/usr/bin/env python3
from gpu_g4g_allocation_model import build_model

model = build_model()
assert model["execution_allowed"] is False
assert len(model["classes"]) == 13
assert sum(item.get("registered", False) for item in model["classes"]) == 4
assert sum(item["class"] == "view-like-auxiliary" for item in model["classes"]) == 4
assert all(item["address"] == "unresolved" for item in model["classes"])
assert all(item["lifetime"][-1] == "release" for item in model["classes"])
print("PASS: J81 allocation classes and lifetimes remain execution-disabled")
