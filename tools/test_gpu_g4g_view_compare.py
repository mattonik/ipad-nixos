import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_view_plan import build_plan, compare_plans


def main():
    bases = (0x10000000, 0x1000F000, 0x10013000, 0x10014000)
    apple = build_plan(view_bases=bases, ownership=("physical_io",) * 4,
                       cache_modes=("unknown",) * 4)
    orchard = build_plan(view_bases=bases, ownership=("orchard_fw_object",) * 4,
                         cache_modes=("uncached",) * 4)
    diff = compare_plans(apple, orchard)
    assert diff["compatible"] is False
    assert diff["execution_allowed"] is False
    assert len(diff["differences"]) == 8
    print("PASS: Apple/Orchard view diff rejects unverifiable attributes")


if __name__ == "__main__":
    main()
