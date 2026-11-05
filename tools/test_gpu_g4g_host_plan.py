#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_host_plan import build_plan
from test_gpu_ldr_inspect import fixture


def main():
    plan = build_plan(fixture())
    assert plan["execution_allowed"] is False
    assert plan["payload_bytes_included"] is False
    assert plan["regions"] == [{
        "kind": "load", "address": 0x1000, "length": 4,
        "address_class": "local/global-low", "crosses_core_code_end": False,
        "address_domain": "unresolved-meta-address", "action": "review-only",
    }, {
        "kind": "zero", "address": 0x2000, "length": 8,
        "address_class": "local/global-low", "crosses_core_code_end": False,
        "address_domain": "unresolved-meta-address", "action": "review-only",
    }]
    assert plan["config_writes"] == [{"address": 0x1234, "value": 5, "action": "review-only"}]
    assert plan["thread_records"] == [[1, 0x2000, 0x1000, 0]]
    assert len(plan["unresolved"]) == 3
    print("PASS: G4G host plan is metadata-only and execution-disabled")


if __name__ == "__main__":
    main()
