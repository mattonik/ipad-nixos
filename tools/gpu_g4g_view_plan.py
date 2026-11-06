#!/usr/bin/env python3
"""Build an execution-disabled Apple four-view registration plan."""

EXPECTED_OFFSETS = (0x00000, 0x0F000, 0x13000, 0x14000)
PROVEN_J81_VIEW_COUNT = len(EXPECTED_OFFSETS)
IOS15_DESCRIPTOR_HINT_COUNT = 8


def build_plan(packed_offsets=EXPECTED_OFFSETS, view_bases=None, ownership=None,
               cache_modes=None, backing_bases=None, map_selectors=None,
               allocator_flags=None):
    offsets = tuple(packed_offsets)
    if offsets != EXPECTED_OFFSETS:
        raise ValueError("packed offsets do not match the recovered J81 layout")
    bases = tuple(view_bases) if view_bases is not None else (None,) * 4
    if len(bases) != 4:
        raise ValueError("four provider view bases are required")
    owners = tuple(ownership) if ownership is not None else (None,) * 4
    caches = tuple(cache_modes) if cache_modes is not None else (None,) * 4
    backing = tuple(backing_bases) if backing_bases is not None else (None,) * 4
    selectors = tuple(map_selectors) if map_selectors is not None else (None,) * 4
    flags = tuple(allocator_flags) if allocator_flags is not None else (None,) * 4
    if any(len(values) != 4 for values in (owners, caches, backing, selectors, flags)):
        raise ValueError("four attributes are required for every view")
    aligned = all(base is None or isinstance(base, int) and base >= 0 and base % 0x1000 == 0
                  for base in bases)
    backing_aligned = all(base is None or isinstance(base, int) and base >= 0 and base % 0x1000 == 0
                          for base in backing)
    distinct = all(view is None or back is None or view != back
                   for view, back in zip(bases, backing))
    complete = (aligned and all(base is not None for base in bases)
                and backing_aligned and all(base is not None for base in backing)
                and distinct
                and all(isinstance(owner, str) and owner for owner in owners)
                and all(isinstance(cache, str) and cache for cache in caches)
                and all(selector == 0x80007 for selector in selectors)
                and all(flag == 0x22 for flag in flags))
    return {
        "execution_allowed": False,
        "complete": complete,
        "descriptor_contract": {
            "proven_j81_view_count": PROVEN_J81_VIEW_COUNT,
            "ios15_hint_count": IOS15_DESCRIPTOR_HINT_COUNT,
            "selected_count": PROVEN_J81_VIEW_COUNT,
            "execution_allowed": False,
        },
        "registrations": [
            {"index": index, "packed_offset": offset, "base_address": base,
             "backing_address": back, "ownership": owner, "cache_mode": cache,
             "map_selector": selector, "allocator_flags": flag}
            for index, (offset, base, back, owner, cache, selector, flag)
            in enumerate(zip(offsets, bases, backing, owners, caches, selectors, flags))
        ],
        "reason": None if complete else "view/backing addresses or mapping attributes are unresolved",
    }


def compare_plans(left, right):
    """Diff two synthetic plans without declaring them hardware-compatible."""
    differences = []
    for lview, rview in zip(left["registrations"], right["registrations"]):
        for field in ("packed_offset", "base_address", "backing_address", "ownership",
                      "cache_mode", "map_selector", "allocator_flags"):
            if lview[field] != rview[field]:
                differences.append({"index": lview["index"], "field": field,
                                    "left": lview[field], "right": rview[field]})
    return {"compatible": not differences and left["complete"] and right["complete"],
            "differences": differences, "execution_allowed": False}


if __name__ == "__main__":
    assert not build_plan()["complete"]
    print("PASS: four-view plan remains execution-disabled")
