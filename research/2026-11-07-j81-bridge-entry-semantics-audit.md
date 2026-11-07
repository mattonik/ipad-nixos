# J81 bridge table entry semantics and one-entry test audit

Date: 2026-11-07

## What the software proves

The 15.8.8 AppleT7000 writer at `FUN_fffffff006c97278` iterates each
`bridge-settings-N` property as a count followed by `(offset, value)` 32-bit
pairs, computes the base from the selector's mapped region, and stores the
value verbatim. The PMGR path does not interpret the value or check a returned
status after the volatile store. The first-pair write was retained as
`0x80010004`; separate fresh-boot no-write peeks read `0x4`. The mismatch
cannot be attributed to PMGR value normalization, but the available captures
do not identify whether it comes from a reset/default baseline or register
semantics. Neither result identifies the high bits or establishes that the
entry is a safe isolated control.

The recovered J81 table has 33 pairs per selector. Pair 0 is at offset
`0x18` and has value `0x80010004`; pair 1 jumps to offset `0x40000` and has
value `0x007c7c01`. Pairs 2–32 are contiguous from `0x40004` through
`0x4007c`. The same 264-byte table is supplied for selectors 9 and 10, mapped
at `0x201f00000` and `0x201f80000`; their contents hash to
`b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4`.
The independent offline audit checks these offsets and mappings against the
J81 ADT. This is a firmware-supplied configuration sequence, not evidence
that every pair is independently safe or read/write.

## Cross-device comparison

The publicly mirrored J82AP device-tree extract has the same byte strings for
`bridge-settings-9` and `bridge-settings-10`, including the `0x40000` entries
(`||`, `y|`, `il`, `rt`, and `yy` in the little-endian byte stream). This
corroborates that the sequence is a deliberate Apple-provided PMGR table and
not a corruption in the local J81 Pongo capture. It supplies no register
field names or semantics and cannot transfer A9 runtime safety evidence to
the A8X. Source: [J82AP device-tree extract](https://gist.github.com/zhuowei/715ded46d018cc7d05265e58d6a65083).

## Is one new entry observation justified?

There is a technically small candidate: on a separate fresh boot, write only
selector 9 pair 1 (`0x201f40000 <- 0x007c7c01`) and immediately read that same
word back, with the existing stage/host-ack/watchdog discipline. It would
answer whether the second mapped word accepts and retains its table value.
It would **not** determine its fields, establish bridge/GPC readiness, or
make later pairs safe. A read-only baseline at that address is also not a
semantic substitute: a baseline value says nothing about whether the write
side effect is harmless.

Do not run that candidate now. The next address is a new register, with no
A8X-specific field contract; Apple applies it as part of the complete clock
provider action, and the existing live history includes a same-boot GPC read
hang after partial bridge state. The separate read-after-write adds another
MMIO transaction in the very block whose hang behavior is uncharacterized.
The watchdog bounds the host wait only if the kernel and hardware watchdog
continue progressing; it has not demonstrated recovery from a stalled
interconnect transaction. Existing tools contain no one-pair write/read
probe, and adding one would only make an unjustified hardware operation
easier to run. No new probe or live runbook is prepared.

The useful path to a discriminating next test is an A8X-specific register
contract (field or access semantics for the bridge window) plus a recovery
mechanism shown to work when that MMIO access stalls. Until then, keep this
table at the validated offline-plan boundary. The complete bridge-table
decision and previous first-pair evidence remain in
`2026-11-07-j81-full-clock-table-test-decision.md` and
`2026-11-06-j81-first-clock-state-readback.md`.
