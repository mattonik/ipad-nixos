import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_view_plan import build_plan


def main():
    missing = build_plan()
    assert missing["execution_allowed"] is False
    assert missing["complete"] is False
    ready = build_plan(view_bases=(0x10000000, 0x10010000, 0x10020000, 0x10030000),
                       backing_bases=(0x20000000, 0x20010000, 0x20020000, 0x20030000),
                       ownership=("synthetic",) * 4, cache_modes=("uncached",) * 4,
                       map_selectors=(0x80007,) * 4, allocator_flags=(0x22,) * 4)
    assert ready["complete"] is True
    assert ready["execution_allowed"] is False
    assert ready["registrations"][1]["packed_offset"] == 0xF000
    assert ready["registrations"][0]["cache_mode"] == "uncached"
    assert ready["registrations"][0]["backing_address"] == 0x20000000
    assert ready["registrations"][0]["map_selector"] == 0x80007
    assert ready["registrations"][0]["allocator_flags"] == 0x22
    assert ready["descriptor_contract"] == {
        "proven_j81_view_count": 4,
        "ios15_hint_count": 8,
        "selected_count": 4,
        "execution_allowed": False,
    }
    assert build_plan(view_bases=(0, 1, 2, 3))["complete"] is False
    assert build_plan(view_bases=(0x1000,) * 4, backing_bases=(0x1000,) * 4,
                      ownership=("synthetic",) * 4, cache_modes=("uncached",) * 4)["complete"] is False
    print("PASS: four-view plan validates and fails closed")


if __name__ == "__main__":
    main()
