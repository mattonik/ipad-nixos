#!/usr/bin/env python3
import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_loader_compare import compare
from test_gpu_ldr_inspect import fixture


def main():
    data = fixture()
    struct.pack_into("<I", data, 44, 0x8000BFF0)
    result = compare(data)
    assert result["start_thread_difference"]["present"] is True
    assert result["start_thread_difference"]["linux_generic"].startswith("constructs")
    assert result["config_difference"]["writes"] == 1
    assert result["apple81_zero_vs_linux"]
    assert result["apple81_zero_vs_linux"][0]["linux"] == "zero-via-segment"
    result = compare(data, 0x1000)
    assert result["apple81_zero_vs_linux"][0]["linux"] == "zero-via-segment"
    print("PASS: Apple/Linux G4G loader comparison is metadata-only")


if __name__ == "__main__":
    main()
