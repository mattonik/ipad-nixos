#!/usr/bin/env python3
"""Static checks for the reserved-memory/no-map fix in linux_dtree_overlay().

Mainline Linux's actual t7001-air2.dtsi declares /memory and /reserved-memory
empty, explicitly commented "To be filled by loader" -- see
research/t7001-handoff-options.md for the full finding. This cannot be
verified end-to-end without hardware (it depends on whether the real DTB pack
actually has a /reserved-memory node to find, and whether this is what was
missing), so these checks only guard the structural invariants: both
reservations are computed from boot_args fields rather than hardcoded
addresses, both are marked no-map, and the framebuffer reservation covers
the same region advertised to the simple-framebuffer node.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# Must look up the real DTB's /reserved-memory node rather than assuming or
# creating one from scratch -- mainline's DTS already declares it empty.
assert '+    node = fdt_path_offset(dtree, "/reserved-memory");' in patch

# Framebuffer reservation: same address/size as the framebuffer node already
# advertised elsewhere in this function, computed from boot_args (not a
# hardcoded per-device constant), marked no-map.
assert '+        siprintf(fdt_nodename, "/memory@%lx", gBootArgs->Video.v_baseAddr);' in patch
assert 'gBootArgs->Video.v_height * gBootArgs->Video.v_rowBytes);' in patch

# Low firmware/TZ reservation: DRAM base up to physBase, guarded against a
# physBase at or below DRAM base, computed from boot_args, marked no-map.
assert '+        if (gBootArgs->physBase > 0x800000000)' in patch
assert '+                fdt_appendprop_addrrange(dtree, 0, node1, "reg", 0x800000000,' in patch
assert '+                                          gBootArgs->physBase - 0x800000000);' in patch

# Both new subnodes must be marked no-map -- the whole point is stopping
# Linux's allocator from reusing this memory, not just describing it.
no_map_count = patch.count('fdt_appendprop(dtree, node1, "no-map", "", 0);')
assert no_map_count == 2, f"expected 2 no-map reservations, found {no_map_count}"

print("t7001 reserved-memory structural checks passed")
