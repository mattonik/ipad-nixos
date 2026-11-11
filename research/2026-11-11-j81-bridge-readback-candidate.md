# J81 bridge readback: selector-10 candidate and limits

Offline review of existing captures and 19H394 bridge traces. No device access.
This identifies a possible narrow comparison, not a validated hardware test.

The working iPadOS trace recorded selector 9 and 10 writer requests on the
GFX provider thread. Both tables begin with `(offset 0x18, value 0x80010004)`.
The captured ADT maps those first entries to `0x201f00018` and
`0x201f80018`, respectively. Linux test4 reached its post-store checkpoint
for both. A checkpoint only shows that execution progressed past the store;
it is not a readback or proof that the target accepted the write.

For selector 9, a fresh no-bridge-write Linux boot read `0x00000004`. Separate
boots read `0x80010004` after the first table write; test4 also read that
value after the complete table and GPC setup. These observations come from
different boots and phases. They do **not** demonstrate a live transition
from the high-bit value to `0x4`, identify the high bits' semantics, or prove
that the register is safe to read under all conditions. The older
[encoding note](2026-11-06-j81-bridge-encoding-conclusion.md) uses the phrase
"live transition" too strongly and should not be interpreted as a captured
same-boot transition.

The nearest symmetric **candidate** is a single read of selector 10's
`0x201f80018` after the already-established Linux full-table/GPC setup. It
could show whether this second bridge reports the planned first word at that
instant. The mirrored offset, identical requested value and successful
selector-9 reads make it a more focused candidate than sweeping the 32 words
at `+0x40000`, but do not establish selector-10 read safety, symmetry, or
register semantics. A mismatch would expose a difference in this Linux
readback; a match would only concern that word and would not establish GPU
readiness. Neither outcome alone compares iPadOS readback or explains the
failed core read.

The Apple bridge writer is a direct store with no readback in the inspected
path. The available source and logs do not provide a field-level A8X contract
or a prior selector-10 `+0x18` read; a search of the saved capture logs found
only write checkpoints for that address. A stalled interconnect read is not
known to be recoverable by watchdog. Before proposing a device run, check for
a source-backed read contract or an existing successful read, and prepare a
one-shot, host-acknowledged capture that preserves boot identity and does not
access the GPU core. Do not treat an unobserved iOS value as equal or replay
new bridge writes on the strength of this analogy.

Evidence: [iOS writer result](2026-11-10-j81-ios-corrected-bridge-result.md),
[thread attribution](2026-11-10-j81-writer-thread-result.md),
[fresh baseline](2026-11-06-j81-fresh-pmgr-bridge-peek.md),
[after-write readback](2026-11-06-j81-first-clock-state-readback.md), and
[test4 audit](2026-11-07-j81-test4-raw-readback-boundary.md).
