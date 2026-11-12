# J81 PMGR timing helper: indirect callback correction

Offline analysis of the local iOS 15 ApplePMGR executable and 19H394
kernelcache. This corrects the `bcc56c` follow-up in
[the GFX dependency analysis](2026-11-08-j81-ios15-gfx-dependencies-and-bridge-apply.md).
No device access or MMIO was needed.

The earlier note describes a PMGR vtable method at `+0x160`. The
decompilation instead loads an **object pointer from the PMGR object field**
at `param_1+0x160` and calls that object's vtable slot `+0xe8`. On the
`param_2+0x57 != 0` branch, it passes function address
`0xfffffff006bd6328`, action 1, and a stack argument constructed from
`param_2+0x30`. The other branch reads through `param_2+0x28`. The
returned value participates in transition timing bookkeeping; the field
names, runtime branch and called object's class are not established.

The existing Ghidra project incorrectly merges `bd6328` into the preceding
function `bd62b0`: instruction `bd6320` returns, and a distinct prologue
starts at `bd6328`. The instructions at `bd635c`–`bd6390` dispatch action
1 through 5 using a five-byte table at `0xfffffff005a52df2` and base
`0xfffffff006bd6394`. The independently read bytes from the 19H394 full
kernel image are `00 48 19 2d 3b`, so action 1 indexes the first byte and
branches to `bd6394`. This is a static code/data finding, not proof that
the callback executes or that its arguments are valid in the captured boot.

At `bd6394`, the action-1 path validates an index and calls `be4488`.
The latter calls `bcf7f0` twice with ordinary PMGR region selector 7,
instance 0, and offsets `(index << 4)` and `(index << 4) | 8`.
`bcf7f0` resolves a mapping and loads a 64-bit value from each offset.
The results are packed into the callback's output. The index comes from
runtime records and was not resolved for the GFX transition. Region
selector 7 has not been independently tied to a live physical mapping in
this callback; do not select an address based on the selector alone.

This means the callback branch **can perform MMIO reads**; it should not be
classified as pure bookkeeping with no hardware access. It does not show
an MMIO write, a clock/reset effect, an effect on page-5 bit 30, or a cause
of the Linux GPU read's non-completion. The `+0x28` path, the action
dispatcher object and runtime call ordering also remain unresolved. The
`19H394` and `19H422` prelinked executable ranges are byte-identical, but
their data segments differ and static parity does not prove runtime binding.
An additional test must first establish a specific reachable target and
meaningful comparison; these instructions do not justify a new MMIO read.

Private instruction and decompiler output is under
`artifacts/live/private/gpu-offline/pmgr-bcc56c-callback-audit/`. Relevant
cross-build scope is documented in
[19H394 code parity](2026-11-11-j81-19h394-code-parity.md).
