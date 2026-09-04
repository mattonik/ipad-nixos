#!/usr/bin/env python3
"""Static checks for Step 7 (v10): moving the ~41 MiB kernel+DTB copy out of
linux_boot()'s low-level, post-teardown context and into the entry marker
stub itself, run *after* the marker has already painted the screen.

This cannot exercise any of these on real hardware (they depend on live
device state and a physical framebuffer), so it only checks structural
invariants: the marker is staged after the kernel+DTB blob is known (not
before, as in Step 6), the staged blob is cache_clean()'d before being
handed to the marker as its physical copy source, linux_boot() no longer
performs the big copy itself for T7001, and the marker stub still never
touches x0, still ends with a br, and now also invalidates the icache
after writing the copied kernel (since it just wrote fresh executable
code) before jumping into it.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# --- Entry point safety margin -------------------------------------------
# 0x810000000 (256 MiB from DRAM base) was chosen after real captured ADTs
# showed iBoot's own memory-map ending as high as ~96 MiB on some A8-family
# units -- comfortably clears every observed case. Must not still be the
# old 0x803000000 (only 48 MiB in, shown to be too close for comfort).
assert "gEntryPoint = (void *)0x810000000;" in patch
assert "gEntryPoint = (void *)0x803000000;" not in patch

# --- Generic ADT memory-map reservation -----------------------------------
assert "static int reserve_memmap_region_cb(" in patch
# SEPFW is explicitly skipped (kept on its existing fdt_add_mem_rsv
# treatment, which matches AsahiLinux/m1n1's deliberate choice not to mark
# it no-map) -- must not be double-reserved as no-map too.
assert '!strcmp(key, "SEPFW")' in patch
assert 'fdt_appendprop(arg->dtree, node1, "no-map", "", 0);' in patch
assert "dt_parse(memory_map, -1, NULL, NULL, NULL, &reserve_memmap_region_cb, &arg);" in patch

# --- Entry marker stub -----------------------------------------------------
assert "+.global _t7001_entry_marker\n" in patch
assert "+.global _t7001_entry_marker_end\n" in patch

# x0 (the DTB physical address) must never be written by the stub -- the
# real kernel needs it intact. Scan only the assembly instruction lines
# (added lines inside the .S file's .text section, before marker_data).
s_start = patch.index("t7001_entry_marker.S")
data_start = patch.index("marker_data:", s_start)
asm_body = patch[s_start:data_start]
instruction_lines = [
    line for line in asm_body.splitlines()
    if line.startswith("+    ") and not line.strip().startswith("+//")
]
for line in instruction_lines:
    # Reject any instruction that writes to x0 as a destination register
    # (first operand after the mnemonic). Comments may mention x0 freely.
    code = line.split("//")[0]
    assert not any(
        code.strip().startswith(op) and "x0," in code.replace(" ", "")
        for op in ("mov", "str", "ldr", "add", "sub")
    ), f"marker stub must never write x0: {line!r}"

# The stub must branch to the real kernel entry rather than falling off
# the end or looping forever -- confirms it's designed to hand off, not
# just observe (unlike the v1-v3 diagnostic-only markers).
assert "+    br   x9" in patch

# --- v10: the marker now performs the kernel+DTB copy itself, after it
# has already painted the framebuffer and held -- so a watchdog reset
# during that copy can no longer prevent the marker from ever being seen,
# unlike Step 6 where the copy happened earlier, in linux_boot(), before
# any jump at all. ------------------------------------------------------
assert "kernel_dest" in asm_body or "kernel destination" in asm_body
assert "kernel_src" in asm_body or "kernel source" in asm_body
# A real word-copy loop: load from the source register, store to the dest
# register, both post-incremented by 4 (32-bit words).
assert "ldr  w18, [x15], 4" in patch
assert "str  w18, [x16], 4" in patch
# Freshly-written code needs an icache invalidate + full barrier sequence
# before it's safe to branch into -- mirrors jump_to_image.S's own
# sequence before its jump.
assert "ic   iallu" in patch
assert "dsb  sy" in patch
assert "isb" in patch

# --- marker_data layout: 40 bytes now (was 32 in Step 6), with the two
# new kernel_src/kernel_copy_words fields appended after kernel_dest. ----
assert "marker_size - 40" in patch
assert "marker_size - 32" not in patch

# --- linux_prep_boot(): the marker must be staged *after* gLinuxStage/
# gLinuxStageSize are known (Step 6 staged it earlier, before the kernel
# was even decompressed, so it could only ever paint the screen -- it had
# no way to know the copy's source/length yet). ---------------------------
prep_start = patch.index("void linux_prep_boot()")
prep_body = patch[prep_start:patch.index("void linux_boot()", prep_start)]
stage_kernel_pos = prep_body.index("linux_stage_kernel(&gLinuxStageAllocation")
marker_alloc_pos = prep_body.index("alloc_contig(marker_alloc_size)")
assert marker_alloc_pos > stage_kernel_pos, (
    "marker must be staged after the kernel+DTB blob is staged, so it can "
    "capture the real copy source/length"
)

# The staged blob is explicitly flushed to physical memory before the
# marker (which reads it back via physical addressing, much later) is
# handed its address -- must happen while gLinuxStage is still the
# cacheable VA, i.e. before its translation to physical addressing.
cache_clean_pos = prep_body.index("cache_clean(gLinuxStage, gLinuxStageSize)")
translate_pos = prep_body.index("- kCacheableView + 0x800000000")
assert cache_clean_pos < translate_pos, (
    "gLinuxStage must be cache_clean()'d while still a cacheable VA, "
    "before its translation to a physical address"
)
assert cache_clean_pos < marker_alloc_pos

# --- linux_boot(): T7001 no longer copies the kernel here -- only the
# marker. The big memcpy((void*)((uint64_t)gEntryPoint + ...), gLinuxStage,
# gLinuxStageSize) that Step 6 ran unconditionally must now be reachable
# only on the non-T7001 (A10) path. --------------------------------------
boot_start = patch.index("void linux_boot()")
boot_body = patch[boot_start:]
boot_body = boot_body[:boot_body.index("\n+}\n+}\n") + len("\n+}\n+}\n")] if "\n+}\n+}\n" in boot_body else boot_body[:2000]
assert "if (socnum == 0x7001) {" in boot_body
assert "return;" in boot_body
# The T7001 branch, up to its own return, must not contain the big-blob
# memcpy -- only the marker copy. (gLinuxStageSize alone, used only for
# the gTopOfKernelData bookkeeping, is fine -- it's gLinuxStage, the
# buffer itself, that must not appear as a copy source here.)
t7001_branch = boot_body[boot_body.index("if (socnum == 0x7001) {"):boot_body.index("return;")]
assert "gLinuxStage," not in t7001_branch and ", gLinuxStage)" not in t7001_branch
assert "memcpy(gEntryPoint, gLinuxMarkerStage, gLinuxMarkerStageSize);" in t7001_branch

# --- Kernel placement doesn't overlap the marker's reserved space --------
assert "gLinuxKernelOffset = 0x200000;" in patch
assert "(uint64_t)gEntryPoint + gLinuxKernelOffset" in patch

print("t7001 entry marker / generic reservation / entry point / v10 kernel-copy-in-marker checks passed")
