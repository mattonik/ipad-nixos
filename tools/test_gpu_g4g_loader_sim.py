#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_loader_sim import simulate
from test_gpu_ldr_inspect import fixture


def main():
    result = simulate(fixture())
    assert result["execution_allowed"] is False
    assert result["firmware_bytes_copied"] is False
    assert result["mmio_operations"] == 0
    assert result["summary"] == {
        "load_reviews": 1, "zero_reviews": 1, "skipped_zeros": 0,
        "config_reviews": 1, "thread_reviews": 1,
    }
    assert all(op["op"].endswith("review") for op in result["operations"])
    print("PASS: G4G simulator is execution- and MMIO-free")


if __name__ == "__main__":
    main()
