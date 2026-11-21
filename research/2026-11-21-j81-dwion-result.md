# J81 DWI-on before GFX activation: result (2026-11-21, run 1)

Recipe: no-core bundle (module 4827876e, core read disabled), PMGR writes in Apple's
order, then ONE write of the DWI power state (0x20e020120: 0x200 -> 0xff, readback
target 15 actual 15, guarded: refuses unless it reads exactly 0x200), post-DWI
snapshot (no other PMGR word changed), single GFX activation, compressed batch.
Boot was fresh (preflight GO). First launch aborted harmlessly: I pre-created the log
directory and the runner refuses an existing one; nothing reached the iPad.

## Result
- DWI PS: S5 0x200 -> SDWI 0xff, stayed 0xff through activation, batch and +10 s.
- GFX voltage word 0x2300c: 0x164 after activation (as before).
- PMIC buck row 0x0128 (candidate GPU rail), before batch: 00 00 40 00 ...;
  after batch: **64 00 64 00 ...**; after 10 s: **64 00 64 00 ...** (held).
  Previously (DWI off, Nov 21 snapshot) this row never left 00/40.
- Row 0x0100 moved 6d -> 88 -> 6d (transient); rows 0x0150 and 0x01c8 unchanged.
- GPC poll ok (29 polls), page5 first sample 0x40000000, batch returned normally, no hang.

## Reading
With DWI on, the GFX rail request reaches the PMIC and row 0x0128 follows it to 0x64/0x64.
Caveats unchanged: 64/64 is not proof of power-good or a ramped voltage, and
buck 1 = GPU rail is an inference. This run had no core read, so it says nothing yet
about the 0x201000020 hang.

## Next
Run the core-read variant on the identical recipe (module d... core build, same DWI step).
Logs: artifacts/live/private/j81-linux-dwion-results-20261121-run1 (private).
