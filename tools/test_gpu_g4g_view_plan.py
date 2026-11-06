import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_view_plan import build_plan


def main():
    missing = build_plan()
    assert missing["execution_allowed"] is False
    assert missing["complete"] is False
    ready = build_plan(view_bases=(0x10000000, 0x10010000, 0x10020000, 0x10030000),
                       ownership=("synthetic",) * 4, cache_modes=("uncached",) * 4)
    assert ready["complete"] is True
    assert ready["execution_allowed"] is False
    assert ready["registrations"][1]["packed_offset"] == 0xF000
    assert ready["registrations"][0]["cache_mode"] == "uncached"
    assert build_plan(view_bases=(0, 1, 2, 3))["complete"] is False
    print("PASS: four-view plan validates and fails closed")


if __name__ == "__main__":
    main()
