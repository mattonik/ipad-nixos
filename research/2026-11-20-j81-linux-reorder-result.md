# Linux reordered test (Apple's start order): result (2026-11-20, boot 3e69fa2d-b78f-4fa2-bd1d-67a64ccc3171)

Plan: `2026-11-20-j81-linux-reorder-plan.md`. One boot, one shot. MiscACG store, voltage-manager check, +0x2d000 store, all BEFORE the GFX cycle (GFX off, PS 0x300, at S0..S2); then cycle, bridge plan, GPC, core read.

| Snapshot | GFX PS 0x20320 | MiscACG | +0x2d000 | +0x2d100 | 0x23000 | vm_sram 0x23004 | page 5 +4 | perf 0x1c200 | 0x2300c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S0 | 0x300 | 0 | 0 | 0 | 1 | 0x170 | 0 | 0x80000000 | 0 |
| S1 (after MiscACG) | 0x300 | 1 | 0 | 0 | 1 | 0x170 | 0 | 0x80000000 | 0 |
| S2 (after +0x2d000) | 0x300 | 1 | 1 | 1 | 1 | 0x180 | 0 | 0x80000000 | 0 |
| A (after GFX cycle) | 0x3ff | 1 | 1 | 1 | 1 | 0x170 | 0 | 0x80000000 | 0 |
| B (after bridge) | 0x3ff | 1 | 1 | 1 | 1 | 0x170 | 0 | 0x80000000 | 0 |
| C (after GPC batch) | 0x3ff | 1 | 1 | 1 | 1 | 0x170 | 0x40000000 | 0x80110100 | 0x164 |

Both guarded stores succeeded (old 0, new 1). The voltage manager (0x23000, bits 11:8) was already clear. Both bits survived the GFX cycle and the bridge plan. GPC poll raw 1 after 11 polls; page-5 bit 30 high on both samples. Then the gated core-ID read: all gates read (GFX PS, MiscACG, page 5, GPC state, GPC control), `stage=before-gpu-revision` and **no result**: hang, watchdog reset, iPad back on iPadOS. Same failure as every earlier Linux attempt.

## Reading
Ordering is not the missing piece on J81: with Apple's order (MiscACG, voltage-manager check, SoC TVM, all before GFX power-on) the core read at 0x201000020 still hangs. The report from the T7000 device does not carry over to A8X with this recipe, in either ordering (this and the earlier after-GFX run).
Observations that differ from the T7000 report: vm_sram (0x23004) is already 0x170 before any store (not 0); the +0x2d000 store moves it only transiently (0x180 at S2, back to 0x170 after the GFX cycle, never the 0x14c-like drop reported); +0x2d100 goes 0 -> 1 (the report: 0x00505000 -> 0x004c5003). A8X is a different chip (iPadOS core ID 0x00070500 vs the report's 0x00030a00), so differing PMGR values are plausible.
Still untested on J81: CPU TVM (0x202220048), DPE throttle, other PMGR startup stores not in the report, the CPU mapping of the aperture (the prepared mapping-only observation answers that one without touching the GPU), and the page-1/page-4 request words (iPadOS requests 0x40480348/0x48480348, no iPadOS readback exists).

Raw: `artifacts/live/private/j81-linux-reorder-results-20261120-run1/` (git-ignored).
