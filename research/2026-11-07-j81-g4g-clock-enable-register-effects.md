# J81 G4G provider clock enable: registers and test4 boundary

Offline trace from the original iOS 8.1 (12B410) disassembly and the saved
test4 captures. No device access or builds were used.

## Provider path and edge condition

In `FUN_ffffff80032935a0`, after the base probe and G4G property hook succeed,
the retained `AppleARMIODevice` provider receives `+0x560(true, 0)` followed
by `+0x568(true, &local, 0)`. The binding trace identifies these as
`enableDeviceClock` and `enableDevicePower`; `clock-gates[0]` and
`power-gates[0]` are both device ID 124 (`0x7c`). The callbacks' return codes
are discarded before GPC setup. The power callback's output is initialized
to zero and is used only after the first RGX identity read to select cleanup:
if nonzero, power-off then clock-off.

For clock enable, the provider forwards ID 124 to the T7001IO clock callback
and then the T7000 PMGR clock callback. The latter maintains an ID-indexed
reference count and only queues a state change if the requested active state
differs from its tracked bitmap. Therefore `enable(true)` does not guarantee
that the transition sequence runs: a prior active client can make it a
no-edge call. The PMGR startup path seeds tracked active state from hardware.
Dynamic clients or their runtime order are not known from the static ADT
consumer walk.

## Concrete enable effects when an edge occurs

The matching PMGR device-clock record maps ID 124 to state index 100 and has
special-action flags `0x06`, selectors 9 and 10. The 12B410 deferred apply
routine runs enable phases in this order:

1. Request state 15 at the PMGR power-state word for index 100, physical
   address `0x20e020320` (PMGR mapping base plus offset `0x20320`), then poll
   until the state field matches. The PMGR writer writes the state field and
   preserves/clears fields according to its transition parameters; its
   register readback loop is explicit in `FUN_ffffff80031e7c10`.
2. Apply selector 9, then selector 10. Each is a 33-entry list of 32-bit
   stores to the mapped bridge windows: bases `0x201f00000` and `0x201f80000`,
   with the first pair at `+0x18`, then offsets through `+0x7c` (the list's
   second pair is at `+0x40000`). The direct writer
   `FUN_ffffff80031eb648` loops over the record's offset/value pairs.
3. Call the SoC-busy helper. It always adjusts the in-memory busy count at
   byte `+0x950`. Its display/MCC callback is conditional on feature `+0x980`, byte
   `+0x98c`, a 0↔1 count edge, and a non-null callback at `+0x990`; only a
   successful callback enables its subsequent display/power bookkeeping.

The record's `0x06` flags select bridge action (bit 1) and busy accounting
(bit 2). It does not select the separate bit-3 action that writes PMGR
registers at offsets `0x20290` and `0x20298`, nor the bit-4 helper. Thus those
two register writes should not be attributed to this GFX record's enable.
The bridge action is enable-only; disable reverses the PMGR/action phases but
does not replay the selector tables.

## What test4 actually observed

`clock-cycle-20261107-test4.log` observed a read of `0x20e020320` as
`0x00000300` and a successful generic Linux PMGR cycle (`rc=0`). It is not an
Apple provider callback trace and contains no intermediate register
checkpoints, so it does not establish Apple's per-device refcount edge,
tracked-state comparison, callback output, or exact PMGR transition writes.
The associated `clock-table-20261107-test4.log` records all 66 after-write
checkpoints, selector 9 entries 00–32 followed by selector 10 entries 00–32;
their values and order exactly match the recovered static tables. The helper
issued each planned volatile store and reached its following checkpoint; these
lines are not register readbacks. They are not evidence Apple issued the
stores through its callback path.

The test4 capture therefore leaves unobserved: any Apple-managed transition
of state index 100; Apple clock-reference and tracked-state changes; SoC-busy
software bookkeeping; whether display/MCC conditions fired; and any
callback-dependent side effects. The Linux bridge writer also executes a
barrier after stores, while available Apple decompilation does not establish
an equivalent explicit barrier. These are concrete sequence/control-flow
differences, not evidence that any one missing effect caused the later RGX
read stall. Test4's separate result shows the full tables and GPC state 1
still preceded an incomplete read at `0x201000020`.

Evidence: `artifacts/live/private/gpu-offline/gpc-link.c`,
`provider.c`, `t7001-gates.c`, `t7000-clock.c`, `gfx-clock-special.c`, and
`gfx-clock-instructions.log`; matching record and selector mappings in
`research/2026-11-07-j81-gpc-provider-object-binding.md`; test captures
`artifacts/live/gpu/clock-cycle-20261107-test4.log`,
`clock-table-20261107-test4.log`, and
`research/2026-11-07-j81-core-revision-after-clock-test4.md`.
