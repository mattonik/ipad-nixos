#!/usr/bin/env python3
from pathlib import Path
from gpu_g4g_extract_view_requirements import extract

source = (Path(__file__).parents[1] / "artifacts/live/private/gpu-offline/ios81-init-allocation.c").read_text()
views = extract(source)
assert len(views) == 8, len(views)
assert [(v["size_parameter"], v["size_multiplier"]) for v in views[:4]] == [(3, 0x6c), (4, 0x6c), (5, 0x6c), (6, 0x3594)]
assert all(v["allocator_flags"] == "0x22" and v["map_selector"] == "0x80007" for v in views)
assert all(v["runtime_addresses"] == "unresolved" for v in views)
print("PASS: extracted eight J81 physical-I/O view requirements without addresses")
