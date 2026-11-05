#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_apple_model import build_model
from test_gpu_ldr_inspect import fixture


def main():
    data = fixture()
    struct.pack_into("<I", data, 44, 0x8000BFF0)
    model = build_model(data)
    assert model["execution_allowed"] is False
    assert model["buckets"]["local/global-low"]["bytes"] == 4
    assert model["buckets"]["core-code"]["bytes"] == 8
    assert model["zero_actions"][0]["action"] == "skip"
    assert model["config_write_count"] == 1
    assert len(model["thread_records"]) == 1
    print("PASS: Apple G4G model is allocation-free and execution-disabled")


if __name__ == "__main__":
    main()
