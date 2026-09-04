#!/usr/bin/env python3
"""Static checks for Step 6: the entry-point safety margin, the generic ADT
memory-map reservation, and the entry marker stub.

This cannot exercise any of these on real hardware (they depend on live
device state and a physical framebuffer), so it only checks structural
invariants: the entry point has real margin above what real captured ADTs
show, the generic reservation skips SEPFW (which keeps its existing
treatment) and marks everything else no-map, x0 is never touched by the
marker stub (must reach the real kernel with the DTB pointer intact), and
the kernel is placed after -- not overlapping -- the marker's own space.
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

# --- Kernel placement doesn't overlap the marker's reserved space --------
assert "gLinuxKernelOffset = 0x200000;" in patch
assert "(uint64_t)gEntryPoint + gLinuxKernelOffset" in patch
# The marker is written to gEntryPoint directly (not offset), and its own
# allocation is rounded up to a 16 KiB page -- far under the 2 MiB gap.
assert "memcpy(gEntryPoint, gLinuxMarkerStage, gLinuxMarkerStageSize);" in patch

print("t7001 entry marker / generic reservation / entry point checks passed")
