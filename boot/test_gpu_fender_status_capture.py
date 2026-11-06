#!/usr/bin/env python3
from pathlib import Path

wrapper = Path(__file__).with_name("gpu-fender-status-run.sh").read_text()
collector = Path(__file__).with_name("gpu_fender_status_capture.py").read_text()
assert "insmod /tmp/gpu-fender-status.ko" in wrapper
assert "runtime_status" in wrapper and "runtime_usage" in wrapper
assert "writel" not in wrapper and "201000000" not in wrapper
assert "state" in wrapper and "control" in wrapper and "hold" in wrapper
assert "stage=finished rc=0" in collector
print("PASS: read-only Fender status wrapper and collector contract")
