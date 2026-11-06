#!/usr/bin/env python3
"""Validate a proposed J81 four-view DART plan without programming hardware."""

def build_plan(mapped_bases, backing_bases, iova_bases=None):
    mapped = tuple(mapped_bases); backing = tuple(backing_bases)
    iovas = tuple(iova_bases) if iova_bases is not None else (None,) * 4
    if len(mapped) != 4 or len(backing) != 4 or len(iovas) != 4:
        raise ValueError("exactly four mapped, backing, and IOVA entries are required")
    aligned = lambda values: all(isinstance(v, int) and v >= 0 and v % 0x1000 == 0 for v in values)
    distinct = len(set(mapped)) == 4 and len(set(backing)) == 4
    pairwise = all(m != b for m, b in zip(mapped, backing))
    iova_ready = all(v is not None and isinstance(v, int) and v >= 0 and v % 0x1000 == 0 for v in iovas)
    iova_distinct = iova_ready and len(set(iovas)) == 4
    complete = aligned(mapped) and aligned(backing) and distinct and pairwise and iova_distinct
    return {"execution_allowed": False, "complete": complete,
            "registrations": [{"index": i, "mapped": mapped[i], "backing": backing[i], "iova": iovas[i]}
                              for i in range(4)],
            "unresolved": [] if complete else [
                "four explicit DART IOVA assignments",
                "GPU DART ownership: J81 SGX has no ADT iommu-parent/DART binding; determine whether it bypasses DART",
            ]}
