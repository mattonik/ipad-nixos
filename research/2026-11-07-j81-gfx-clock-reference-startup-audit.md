# J81 GFX clock-reference startup audit (offline, 2026-11-07)

This audit follows the iOS 8.1 PMGR startup path to determine whether it seeds
the per-device clock-reference count before AGX probes. It uses the preserved
12B410 kernelcache and J81 device tree only; no iPad, firmware execution, or
MMIO was involved. It is distinct from the conditional display/MCC action.

## Startup findings

`AppleT7000PerformanceController::start` at
`0xffffff80031e6fc8` installs its power callback, then calls the inherited
`AppleARMPerformanceController::start` through the vtable at
`0xffffff8002695860`, slot `+0x2b8` (`0xffffff800266775c`). The inherited
start reads `device-clocks-min`, allocates the per-record clock-reference
array (`this+0x308`, `param_1[0x61]`) and zeroes it. It separately allocates
and zeroes the per-record companion array at `this+0x310`.

The T7000 start then builds the device-ID-to-record-index map. The GFX
provider uses device ID `0x7c` (124), which maps to the GFX table record; the
clock callback indexes the zeroed reference array by that record index. The
same startup reads PMGR actual-state nibbles into its power-state bitmap
(`FUN_ffffff80031e7cc8`) and reconciles PMGR states (`FUN_ffffff80031e82f4`)
through direct state-transition calls. Those routines do not invoke the
per-device clock callback, so they do not seed this clock-reference count.

The clock callback at `0xffffff80031ea140` increments or decrements the
per-record count. Its derived requested-active state is compared with the
controller's tracked state; only a change queues and flushes the device
transition. For the GFX record, that transition path includes PMGR state
index 100, selector 9 then selector 10, and the SoC-busy reference update.
The display-idle/MCC call is a later conditional action inside busy
accounting. It is not required to identify the separate clock-reference
edge.

## What this says about test4

Test4 manually reproduced the PMGR state and all 66 selector writes, then
performed GPC setup, but it did not call Apple's per-device provider clock
callback. The offline audit therefore identifies a concrete software-state
difference: the hardware replay did not exercise the initialized reference
count's transition path or its busy-reference accounting. Matching register
readbacks does not show that these stateful provider callbacks ran.

If no other service requested GFX clock ID 124 first, AGX's first enable
request would change its initialized count from 0 to 1. The static evidence
reviewed here does not establish whether another consumer made an earlier
request, nor the exact tracked-state value when AGX probes. That keeps the
0-to-1 transition conditional rather than proven for the captured boot.
Likewise, this analysis does not establish that the omitted callback caused
the core-ID read hang or that replaying its action on Linux is safe.

## Evidence and next offline target

Evidence is in the preserved iOS 8.1 artifacts:

- `artifacts/live/private/gpu-offline/t7000-flags.c`:
  T7000 start at `0xffffff80031e6fc8` and state reconciliation.
- `artifacts/live/private/gpu-offline/t7000-clock.c`:
  per-device reference-count and queued transition logic at
  `0xffffff80031ea140`.
- `artifacts/live/private/gpu-offline/clock-table.c`:
  GFX device-ID mapping and initial action/state bookkeeping at
  `0xffffff80031e9af4`.
- `artifacts/live/private/gpu-offline/ARMPlatform.raw` and `T7000.raw`:
  inherited start vtable entry and its target, cross-checked from their raw
  bytes with the existing Ghidra projects.

The next useful offline check is a bounded call-site search for any earlier
consumer of gate ID 124 before the G4G probe. Until that is closed, retain
the clock-reference edge as the best concrete non-MCC difference between
test4 and Apple's path, with its runtime occurrence marked unknown.

## First GFX edge: concrete work and test4 boundary

The callback's relevant reference count is a 32-bit entry in the array at
controller `this+0x308`, selected by the provider's mapped device-record
index. Parent startup zeroes this array. The J81 `sgx` provider wrapper maps
`clock-gates[0]` to device ID 124; the T7000 device table maps 124 to record
index and PMGR state index 100. The count is therefore initialized to zero
for this controller instance, but that alone does not prove it is still zero
when G4G probes: an earlier enable can increment it, and a balanced earlier
disable can decrement it.

On an enable call, the callback increments the count and derives the desired
active state as `count != 0` (the GFX record has no one-shot/count-equality
flag). It compares that result with the controller's tracked active bitmap.
Only a mismatch queues and flushes a transition. For a true 0→1 reference
edge with the tracked GFX bit clear, the enable work is ordered: request PMGR
state index 100 at 15 (the helper writes/polls only if its state checks require
a transition); apply selector 9's
33 offset/value writes; apply selector 10's 33 writes; then increment the
SoC-busy reference count. If the tracked bit is already active, the 0→1
count change does not replay those operations. If another client already
holds a reference, G4G's enable is not a 0→1 edge and likewise does no new
transition. Startup reconciliation initializes the tracked state from actual
PMGR state, so whether the GFX tracked bit is clear at probe time also depends
on boot hardware state. The callback can reconcile a count/state mismatch,
but the available captures do not show Apple's callback inputs.

Test4 established the visible postconditions after its own sequence: PMGR
readback `0x3ff`, all 66 selector writes acknowledged in Apple table order,
GPC state/control `1`/`0x40000000`, and the two post-GPC bridge values. It
did not call the clock provider, mutate Apple's reference count or active
bitmap, execute the controller's queued PMGR transition, or account the busy
reference. Its generic Linux PMGR cycle did issue power-state changes and
reached the same final state word; the captured result cannot establish that
Apple's PMGR helper ran or that its software transition bookkeeping matched.
Thus test4 omitted an Apple software transition path and busy accounting, but
the evidence does not support claiming that it omitted an additional
unreplayed selector-table hardware write. Test4's first RGX identity read at
`0x201000020` still stalled after the direct table replay and GPC setup.

The source-level dispatch is documented in
`2026-11-07-j81-gpc-provider-object-binding.md`; exact test4 outcomes are in
`2026-11-07-j81-core-revision-after-clock-test4.md`. Startup allocation and
state reconciliation are in `t7000-flags.c` / `t7000-map.c`; the reference
callback is `t7000-clock.c`; the phase-ordered transition and selector writer
are described in `gfx-clock-special.c` and the provider-binding note. This
static pass does not close whether any service requested ID 124 before G4G,
whether the controller's tracked state was active at probe time, or whether
the conditional SoC-busy/display path ran. It also does not identify the
cause of the RGX read stall or qualify a new MMIO replay as safe.
