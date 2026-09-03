#!/usr/bin/env python3
"""Static checks for the T7001 pre-jump framebuffer marker stub.

This cannot exercise the marker on real hardware (it draws to a physical
framebuffer that only exists on the iPad), so it only checks the structural
invariants that would otherwise be easy to break silently: the assembly
stub's data offsets must match what linux_prep_boot() patches, the marker
must be staged and cache-cleaned before gLinuxPrepared is set, the T7001
jump must target the marker stub rather than jumping straight into the
kernel, and the current build must default to the isolated spin-forever
test rather than continuing into the kernel jump.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# The stub must exist and export both ends, so linux_prep_boot() can size it.
assert "+.global _t7001_boot_marker\n" in patch
assert "+.global _t7001_boot_marker_end\n" in patch
assert "+_t7001_boot_marker_end:" in patch

# Asm side: ldr offsets into marker_data (framebuffer addr, pixel, count,
# entry, continue flag).
assert "+    ldr  x10, [x9]" in patch
assert "+    ldr  w11, [x9, 8]" in patch
assert "+    ldr  w12, [x9, 12]" in patch
assert "+    ldr  w13, [x9, 24]" in patch
assert "+    ldr  x14, [x9, 16]" in patch

# Zero continue flag must spin forever rather than fall through to the
# kernel branch -- this is the whole point of the isolated test.
assert "+    cbz  w13, 2f" in patch
assert "+2:\n" in patch
assert "+    b    2b" in patch

# The stub must leave x1=x2=x3=0 for the real kernel entry (AArch64 boot
# protocol) on the continue path.
assert "+    mov  x1, 0\n" in patch
assert "+    mov  x2, 0\n" in patch
assert "+    mov  x3, 0\n" in patch

# C side: the same offsets, in the same order, patched before the jump.
# Fill color must not be white/transparent -- the default PongoOS screen is
# light, so a white or fully-transparent fill would be invisible.
assert "*(uint64_t *)(data + 0)  = gBootArgs->Video.v_baseAddr;" in patch
assert "*(uint32_t *)(data + 8)  = 0xff000000u;" in patch
assert "0xffffffffu" not in patch
assert "*(uint32_t *)(data + 12) = (uint32_t)fb_words;" in patch
assert "*(uint64_t *)(data + 16) = (uint64_t)gLinuxStage;" in patch
assert "*(uint32_t *)(data + 24) = 0;" in patch

# The fill must cover the whole framebuffer (v_height * v_rowBytes), not a
# small band -- a tiny patch was the likely reason the first run was
# inconclusive.
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
