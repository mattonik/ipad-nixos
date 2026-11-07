# J81 test4 bridge replay versus iOS 8.1 clock action

Offline comparison of test4 artifacts with the matching iOS 8.1 (12B410) J81
clock record. No hardware was accessed for this comparison.

## Exact table match

The staged test4 plan
`artifacts/live/gpu-test-bundle-20261107-core-revision/data/gfx-bridge-plan.bin`
has SHA-256
`1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435`.
It is 528 bytes: 66 little-endian `(u32 offset, u32 value)` pairs. Decoding
all 66 pairs and comparing them against `writes` in
`artifacts/live/private/gpu-offline/gfx-bridge-static-plan.json` gives an exact
match. That static table's recorded content digest is
`b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4`.

The matching iOS 8.1 clock record has device ID `0x7c`, PMGR state index 100,
special flags `0x06`, and selectors 9 and 10. Each selector has 33 pairs;
Apple's table application order is selector 9 then selector 10. The plan maps
them to bases `0x201f00000` and `0x201f80000`; both start at offset `0x18`
with `0x80010004`, then continue at `0x40000` through `0x4007c`. Test4's
`clock-table-20261107-test4.log` records `after-bridge-9-00` through `-32`,
then `after-bridge-10-00` through `-32`, all completed. Therefore there is no
table-value, table-order, or missing-pair discrepancy in the replay.

## Sequence effects not reproduced

In the original 12B410 action, `FUN_ffffff80031ea58c` applies selector 9 and
then selector 10 on enable, followed by the flag-bit-2 SoC-busy helper
`FUN_ffffff80031eb7c0`. The GFX flags are `0x06`; test4 replayed the two
selector tables but did not call Apple's per-device provider clock callback
or its busy-reference transition. The helper always updates the software busy
count. Its display-idle/MCC call is further conditional on the initialized
feature flag, a 0-to-1/1-to-0 edge, and a resolved display callback. Test4
has no observations of those runtime inputs, so the missing busy transition
is a concrete sequence difference but not evidence that display/MCC work
caused the RGX read stall.

The Linux replay executes a volatile 32-bit store and `__sync_synchronize()`
after each table write (`boot/gpu-bridge-once.c`); the host then acknowledges
each checkpoint before the next operation. The recovered Apple writer
`FUN_ffffff80031eb648` is a direct store loop in
`artifacts/live/private/gpu-offline/gfx-clock-special.c`. The available
decompilation does not establish whether the original instruction stream has
an explicit barrier, so MMIO completion/ordering equivalence is unresolved.
The Linux-side barrier does not reproduce Apple's provider busy bookkeeping.

## Evidence scope

Original-sequence evidence: `artifacts/live/private/gpu-offline/gfx-clock-special.c`
and `gfx-clock-instructions.log` (12B410 `T7000.raw`), plus
`research/2026-11-07-j81-gpc-provider-object-binding.md`. Exact planned values:
`artifacts/live/private/gpu-offline/gfx-bridge-static-plan.json` and the
SHA-pinned binary above. Actual test4 ordering/completion:
`artifacts/live/gpu/clock-table-20261107-test4.log`.
