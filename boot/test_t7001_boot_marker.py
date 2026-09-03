#!/usr/bin/env python3
"""Static checks for the T7001 pre-jump framebuffer strobe stub and the
jump_to_image() tramp-buffer fix.

This cannot exercise the strobe or the SRAM-release path on real hardware
(they depend on physical framebuffer state and live SoC registers), so it
only checks the structural invariants that would otherwise be easy to break
silently: the assembly stub's data offsets must match what
linux_prep_boot() patches, the marker and tramp buffers must be staged and
cache-cleaned before gLinuxPrepared is set, the T7001 jump must target the
marker stub with a real tramp buffer (not the kernel directly, and not
tramp=0), and the strobe must re-assert each color repeatedly rather than
writing it once.

History: v1 (small one-shot white band) and v2 (one-shot full-screen black
fill) were both inconclusive on hardware. v3 (infinite black/green strobe,
single delay guess) produced no visible strobe across 12.4s of video, but
the observer reported a brief reddish flash right after sending the
command -- the same reddish, brief signature v1 and v2 also reported
despite three unrelated marker designs, which is why v4 stops tuning the
marker's own visuals and instead fixes jump_to_image's tramp==0 call: its
own source comment warns that path isn't meant for booting a kernel, and
the proven exit_to_el1_image() path used elsewhere in this tree for actual
XNU/Linux boots never passes tramp=0. See docs/project-status.md.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# The stub must exist and export both ends, so linux_prep_boot() can size it.
assert "+.global _t7001_boot_marker\n" in patch
assert "+.global _t7001_boot_marker_end\n" in patch
assert "+_t7001_boot_marker_end:" in patch

# Asm side: ldr offsets into marker_data (fb addr, color A, color B, delay,
# word count, repeat count).
assert "+    ldr  x10, [x9]" in patch
assert "+    ldr  w15, [x9, 20]" in patch
assert "+    ldr  w13, [x9, 24]" in patch
assert "+    ldr  w11, [x9, 8]" in patch
assert "+    ldr  w4, [x9, 16]" in patch
assert "+    ldr  w11, [x9, 12]" in patch

# Each color phase must re-fill (loop back on the repeat count) before
# switching color, and the outer loop must never branch onward to a kernel.
assert "+    subs w13, w13, 1" in patch
assert "+    b    1b" in patch
assert "+    br " not in patch, "the strobe stub must never branch onward to the kernel"

# C side: fb address, colors chosen to survive an unknown a8b8g8r8
# channel-order assumption, and the repeat-count field.
assert "*(uint64_t *)(data + 0)  = gBootArgs->Video.v_baseAddr;" in patch
assert "*(uint32_t *)(data + 8)  = 0xff000000u;" in patch
assert "*(uint32_t *)(data + 12) = 0xff00ff00u;" in patch
assert "*(uint32_t *)(data + 20) = (uint32_t)fb_words;" in patch
assert "*(uint32_t *)(data + 24)" in patch  # repeat count, patched to a nonzero value
assert "0xffffffffu" not in patch

# The fill must cover the whole framebuffer (v_height * v_rowBytes), not a
# small band.
assert "uint64_t fb_words = (gBootArgs->Video.v_height * gBootArgs->Video.v_rowBytes) / 4;" in patch

# The marker and tramp buffers must be cache-cleaned, and gLinuxPrepared
# must only flip true after both -- otherwise a failed/incomplete stage
# could still jump.
marker_clean_at = patch.index("cache_clean(marker_alloc, marker_alloc_size);")
tramp_clean_at = patch.index("cache_clean(tramp_alloc, 0x4000);")
prepared_at = patch.index("gLinuxPrepared = true;")
assert marker_clean_at < prepared_at, "gLinuxPrepared must be set after the marker is staged and cleaned"
assert tramp_clean_at < prepared_at, "gLinuxPrepared must be set after the tramp page is staged and cleaned"

# The T7001 jump must target the marker stub with a real tramp buffer, not
# the kernel Image directly, and not tramp=0.
assert "jump_to_image((uint64_t)gLinuxMarkerStage, (uint64_t)gLinuxDtb, (uint64_t)gLinuxTrampStage);" in patch
assert "jump_to_image((uint64_t)gLinuxStage, (uint64_t)gLinuxDtb, 0);" not in patch
assert "jump_to_image((uint64_t)gLinuxMarkerStage, (uint64_t)gLinuxDtb, 0);" not in patch

print("t7001 boot marker structural checks passed")
