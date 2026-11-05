#!/usr/bin/env python3
"""Check the first-write probe remains a single, guarded MMIO operation."""
from pathlib import Path

source = Path(__file__).with_name("gpu-bridge-first.c").read_text()
wrapper = Path(__file__).with_name("gpu-bridge-first-run.sh").read_text()
assert source.count("0x80010004") == 3
assert source.count("201f00018") == 1
assert source.count("0x80010004; __sync_synchronize") == 1
assert "gpu-bridge-first.once" in source
assert "runtime_usage)\" = 1" in wrapper
assert "^/dev/" in wrapper and "gpu-pmgr-peek" in wrapper
print("PASS: first-write probe is one-shot, identity-gated and storage-free")
