#!/usr/bin/env python3
"""Build an execution-disabled Apple four-view registration plan."""

EXPECTED_OFFSETS = (0x00000, 0x0F000, 0x13000, 0x14000)


def build_plan(packed_offsets=EXPECTED_OFFSETS, view_bases=None):
    offsets = tuple(packed_offsets)
    if offsets != EXPECTED_OFFSETS:
        raise ValueError("packed offsets do not match the recovered J81 layout")
    bases = tuple(view_bases) if view_bases is not None else (None,) * 4
    if len(bases) != 4:
        raise ValueError("four provider view bases are required")
    aligned = all(base is None or isinstance(base, int) and base >= 0 and base % 0x1000 == 0
                  for base in bases)
    complete = aligned and all(base is not None for base in bases)
    return {
        "execution_allowed": False,
        "complete": complete,
        "registrations": [
            {"index": index, "packed_offset": offset, "base_address": base}
            for index, (offset, base) in enumerate(zip(offsets, bases))
        ],
        "reason": None if complete else "runtime provider view bases are unresolved",
    }


if __name__ == "__main__":
    assert not build_plan()["complete"]
    print("PASS: four-view plan remains execution-disabled")
