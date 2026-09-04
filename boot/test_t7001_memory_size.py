#!/usr/bin/env python3
"""Static checks for the /memory@800000000 size fix.

Mainline's Apple device trees ship /memory's "reg" as literally zero-sized
(<0x8 0 0 0>, "To be filled by loader"), and this project's real boot path
never filled it in (the only code that used to, linux_dtree_init(), is
confirmed dead -- see docs/project-status.md Round 3 and the Step 6 entry).
A kernel told it has zero bytes of RAM fails in memblock/mm init before any
console could work, which would explain the silent-hang symptom of every
attempt so far, independent of the jump mechanism or reserved-memory work.
This cannot be verified end-to-end without hardware, so this only checks the
structural invariants: the placeholder is actually cleared before the real
value is set, the real value is computed from boot_args (not a hardcoded
constant), and it runs unconditionally (this bug isn't T7001-specific).
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
patch = (root / "boot" / "pongo-t7001.patch").read_text()

# Must look up the real /memory node, not create one from scratch --
# mainline's DTS already declares it (with reg=0).
assert '+    node = fdt_path_offset(dtree, "/memory@800000000");' in patch

# The zero-sized placeholder must be deleted before the real value is
# appended -- fdt_appendprop_addrrange() appends to an existing property
# rather than replacing it, so skipping the delete would leave a stray
# zero-sized entry alongside the real one.
delprop_at = patch.index('fdt_delprop(dtree, node, "reg");')
appendprop_at = patch.index(
    'fdt_appendprop_addrrange(dtree, 0, node, "reg", 0x800000000, mem_size);'
)
assert delprop_at < appendprop_at, "the placeholder must be deleted before the real size is appended"

# Computed from boot_args, not a hardcoded constant, and matches the same
# top-of-RAM margin the dead linux_dtree_init() code used to apply.
assert "uint64_t mem_size = (gBootArgs->memSize - 0x02000000ull) & ~0x1FFFFFull;" in patch

# Must run inside linux_dtree_overlay(), not gated behind any socnum check
# -- this bug affects any chip booting through this patch, not just T7001.
# linux_dtree_overlay() itself has no socnum guard anywhere in its body, so
# checking the fix lands inside that function (not linux_prep_boot(), which
# does have T7001-only sections) is sufficient.
overlay_start = patch.index("bool linux_dtree_overlay(")
overlay_end = patch.index("bool linux_can_boot()", overlay_start)
assert overlay_start < delprop_at < overlay_end, "the memory-size fix must live inside linux_dtree_overlay(), unconditionally"

print("t7001 memory size structural checks passed")
