#!/usr/bin/env python3
from gpu_g4g_dart_plan import build_plan

m = [0x10000000, 0x1000f000, 0x10013000, 0x10014000]
b = [0x800000000, 0x800010000, 0x800020000, 0x800030000]
assert not build_plan(m, b)["complete"]
plan = build_plan(m, b, [0x40000000, 0x40010000, 0x40020000, 0x40030000])
assert plan["complete"] and plan["execution_allowed"] is False
try: build_plan(m, b, [0x40000000] * 4)
except ValueError: raise AssertionError("duplicate IOVAs should be represented as incomplete")
except Exception: pass
else: assert not build_plan(m, b, [0x40000000] * 4)["complete"]
print("PASS: J81 DART plan validates four distinct IOVAs without hardware access")
