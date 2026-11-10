# J81 GPC setup versus page-5 bit 30: cross-OS audit

Offline audit of the 19H394 iOS four-point capture, the existing Linux
post-GPC capture, the inspected iOS 15.8.8 G4G disassembly, and the Linux
helper source. No hardware access.

## Actual observations

The 19H394 iOS probe logged PMGR poll `0x3ff`, GPC poll `0x1`, and GPU
identity `0x70500`. Its PMGR-method region 0 offset `0x5004` was `0` just
after the power-provider return and `0x40000000` at the successful GPC poll.
The latter sample and the post-provider sample were buffered and emitted
later at identity. The iOS GPC control value and individual setup stores were
not traced in this boot. iOS physical addresses are inferred from the Pongo
ADT, not independently verified runtime mappings.

On Linux boot `ccd9bd5c-cf93-4ba3-b4ce-40d05858d400`, the GPC helper read
initial state `0`, then reached before/after checkpoints for these stores in
order: `0x201e10000 <- 0xffff0000`, `0x201e00000 <- 0x40000000`, and
`0x201e01000 <- 0x11`. Its first poll read returned `0x1`. The watchdog was
disarmed. A later guarded page-5 read on that same boot returned `0` at
`0x20e005004`, with watchdog disarmed. The page-5 sample followed completion
of the GPC helper; its precise time relative to the poll is not recorded.
The GPC helper's after-store values are local plan values, not readbacks. The
post-GPC run did not independently read its control register. A different
Linux boot (test4) did read control `0x40000000` after GPC setup; do not
substitute that readback for this boot.

## What the setup comparison supports

The iOS 15.8.8 static G4G path with `has-kf` clear issues the same three
values in the same order and polls bit 4 clear. The captured J81 ADT lacks
`gfx-kf`, but the exact 19H394 boot's individual GPC writes and runtime
property branch were not recorded. The iOS poll `0x1` and Linux poll `0x1`
are actual observed reads on different boots; they do not imply that the
remaining state or mappings are equivalent. No claim of equal GPC control
readback across these two captures is supported.

The Linux helper inserts a host acknowledgment and a full memory barrier
around every access, unlike the inspected short iOS instruction sequence.
The Linux page-5 sample comes from a later separate supervised operation,
whereas iOS samples immediately after the poll. We do not have timing to
quantify either gap or to tell whether the page-5 bit changed and later
cleared on Linux. Conversely, initial boot state, concurrent activity,
provider state, ordering and register side effects may differ. The observed
bit is not established as a GPU-ready predicate.

## Next discriminating measurement

A same-boot iOS sample after the GPC control write but before the `0x11`
state request would split the observed post-provider to post-poll interval.
It would not distinguish time-dependent or concurrent transitions from the
preceding stores and adds another undocumented read, so it should retain
early/post-provider/post-poll controls and bounded logging. A Linux timing
comparison would need a separately reviewed, supervised same-process design
and explicit per-read checkpoints: the current Linux one-shot cannot provide
an immediate second sample. Neither result alone justifies writing page 5
or repeating the stalled core identity access.

Inputs: `artifacts/live/gpu/page5-postgpc-20261110-01/` (private capture),
[power-boundary iOS result](2026-11-10-j81-page5-capture-results.md#power-provider-boundary-change-observed-during-gpc-interval),
[iOS static sequence](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md), and
`boot/gpu-gpc-init.c`.

## Follow-up: the saved Linux capture has a timing clue

On 2026-11-10, a re-audit of the current local artifacts found that
`gpc.log` contains `host-stage time_ns=1794313835258631000` for the `0x1`
poll, while the local filesystem reports the page-5 log's birth time as
approximately `1794313886097255936` ns: about **50.84 seconds later**. Its
modification time is about 0.05 seconds after that. The page-5 capture script
opens this log with `O_CREAT|O_EXCL` before sending its command, then awaits
the before-read checkpoint and host acknowledgment before the load. If these
are the original file creation times and the host wall clock did not jump,
the read occurred at least roughly 50.8 seconds after the host observed the
poll. File metadata is weaker evidence than a monotonic timestamp saved in
both logs and could change if artifacts were copied or recreated; the exact
MMIO interval was not instrumented.

The host's recorded after-store to next after-store gaps for control, state
request and poll were about 2.0 and 2.3 ms respectively, again host receipt
times rather than bus transaction timestamps. This is far from an immediate
post-poll sample. The Linux `0` therefore cannot rule out a brief set-and-clear
of bit 30, and a late iOS sample alone would not resolve Linux behavior.

The most informative next comparison is a fresh Linux GFX/GPC control boot
that records a bounded page-5 sample immediately after the successful GPC
poll, then (on a separate boot or under a separately reviewed repeated-read
plan) compares a delayed sample. Preserve the host-acknowledged checkpoints,
watchdog and one-shot guard, verify exact boot/module identity, and do not
access GPU core registers or write page 5. A non-acknowledged or stalled
sample is inconclusive, not zero. This is a proposed design, not an already
built or hardware-tested probe.

A [subsequent same-process Linux test](2026-11-10-j81-linux-gpc-page5-timed-probe.md#corrected-hardware-result) sampled `0` after the poll, with the sysfs read returning 34.5 µs after a timestamp taken following the poll.
