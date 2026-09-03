#!/usr/bin/env python3
"""Static checks for the T7001 pre-jump framebuffer strobe stub.

This cannot exercise the strobe on real hardware (it draws to a physical
framebuffer that only exists on the iPad), so it only checks the structural
invariants that would otherwise be easy to break silently: the assembly
stub's data offsets must match what linux_prep_boot() patches, the marker
must be staged and cache-cleaned before gLinuxPrepared is set, and the T7001
jump must target the marker stub rather than jumping straight into the
kernel.

v1 (a small one-shot white band) and v2 (a one-shot full-screen black fill)
were both inconclusive on hardware -- see docs/project-status.md. v3
replaces the one-shot fill with an infinite two-color strobe so a future
run gives an unambiguous answer regardless of display double-buffering.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# The stub must exist and export both ends, so linux_prep_boot() can size it.
assert "+.global _t7001_boot_marker\n" in patch
assert "+.global _t7001_boot_marker_end\n" in patch
assert "+_t7001_boot_marker_end:" in patch

# Asm side: ldr offsets into marker_data (fb addr, color A, color B, delay,
# word count).
assert "+    ldr  x10, [x9]" in patch
assert "+    ldr  w15, [x9, 20]" in patch
assert "+    ldr  w11, [x9, 8]" in patch
assert "+    ldr  w4, [x9, 16]" in patch
assert "+    ldr  w11, [x9, 12]" in patch

# It must be an infinite loop -- both color-A and color-B fill/delay
# sequences must exist, and the loop must branch back to itself (b 1b),
# never forward past that into any kernel-entry branch.
assert "+1:\n" in patch
assert "+    b    1b" in patch
assert "+    br " not in patch, "the strobe stub must never branch onward to the kernel"

# C side: the same offsets, colors chosen to survive an unknown a8b8g8r8
# channel-order assumption (opaque black, opaque bright green), and a
# generous delay so each phase is human-visible.
assert "*(uint64_t *)(data + 0)  = gBootArgs->Video.v_baseAddr;" in patch
assert "*(uint32_t *)(data + 8)  = 0xff000000u;" in patch
assert "*(uint32_t *)(data + 12) = 0xff00ff00u;" in patch
assert "*(uint32_t *)(data + 16) = 500000000u;" in patch
assert "*(uint32_t *)(data + 20) = (uint32_t)fb_words;" in patch
assert "0xffffffffu" not in patch

# The fill must cover the whole framebuffer (v_height * v_rowBytes), not a
# small band.
assert "uint64_t fb_words = (gBootArgs->Video.v_height * gBootArgs->Video.v_rowBytes) / 4;" in patch

# The marker must be cache-cleaned, and gLinuxPrepared must only flip true
# after that clean -- otherwise a failed/incomplete stage could still jump.
clean_at = patch.index("cache_clean(marker_alloc, marker_alloc_size);")
prepared_at = patch.index("gLinuxPrepared = true;")
assert clean_at < prepared_at, "gLinuxPrepared must be set after the marker is staged and cleaned"

# The T7001 jump must target the marker stub, not the kernel Image directly.
assert "jump_to_image((uint64_t)gLinuxMarkerStage, (uint64_t)gLinuxDtb, 0);" in patch
assert "jump_to_image((uint64_t)gLinuxStage, (uint64_t)gLinuxDtb, 0);" not in patch

print("t7001 boot marker structural checks passed")
