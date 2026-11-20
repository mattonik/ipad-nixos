# Linux PLL1/PLL4 +8 replay test: result (2026-11-20, boot 5372aa58-7d4e-4ece-a57c-6a48f2c51df5)

Plan: `2026-11-20-j81-queue-runbook.md` step 1. One boot, one shot. Order: MiscACG, voltage-manager check, SoC TVM, PLL1 +0x1008, PLL4 +0x4008, all before GFX power-on, then GFX cycle, bridge plan, GPC batch, gated core-ID read under the watchdog.

| Snapshot | GFX PS | MiscACG | +0x2d000 | +0x2d100 | +0x1008 | +0x4008 | vm_sram 0x23004 | page 5 +4 | perf | 0x2300c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S0 | 0x300 | 0 | 0 | 0 | 0x80480348 | 0x88480348 | 0x170 | 0 | 0x80000000 | 0 |
| S1 (MiscACG) | 0x300 | 1 | 0 | 0 | same | same | 0x170 | 0 | same | 0 |
| S2 (+0x2d000) | 0x300 | 1 | 1 | 1 | same | same | 0x170 | 0 | same | 0 |
| S3 (PLL1) | 0x300 | 1 | 1 | 1 | **0x40480348** | 0x88480348 | 0x170 | 0 | same | 0 |
| S4 (PLL4) | 0x300 | 1 | 1 | 1 | 0x40480348 | **0x48480348** | 0x170 | 0 | same | 0 |
| A (after GFX cycle) | 0x3ff | 1 | 1 | 1 | 0x40480348 | 0x48480348 | 0x170 | 0 | same | 0 |
| B (after bridge) | 0x3ff | 1 | 1 | 1 | same | same | 0x180 | 0 | same | 0 |
| C (after GPC) | 0x3ff | 1 | 1 | 1 | same | same | 0x170 | 0x40000000 | 0x80110100 | 0x164 |

All four guarded stores succeeded with the exact expected readbacks (old 0 / 0 / 0x80480348 / 0x88480348, new 1 / 1 / 0x40480348 / 0x48480348) and persisted through the GFX cycle, the bridge plan and the GPC batch; no link loss, no stop. GPC poll raw 1 after 11 polls, page-5 bit 30 high on both samples. Then the gated core-ID read: GFX PS, MiscACG, page 5, GPC state and control all read and fed, `stage=before-gpu-revision address=0x201000020` and **no result**: hang, watchdog reset, iPad back on iPadOS.

## Reading
Linux now matches the working iPadOS boot on every register we have compared at the matching phases: GFX PS, MiscACG, +0x2d000 (and its status +0x2d100 moving 0->1 after the store), page-1/page-4 +8 words (01 in [31:30]), page 5, GPC state/control, perf, +0x2300c, voltage manager, vm_sram (0x170/0x180, iPadOS value not yet read), and the core page mapping (identical attributes to pages that read fine). The core read at 0x201000020 still hangs. So none of these, singly or together, is the missing step: MiscACG + SoC TVM + the page-1/page-4 pair, set in Apple's order before GFX power-on, are not sufficient on J81. The A8 thread's T7000 recipe does not carry to A8X.
Remaining unmeasured differences: Fender +0 bit 29 on iPadOS (the `fender` probe), CPU TVM 0x202220048 and the DPE words (CPU-block probes), iPadOS +0x2d100 / vm_sram / +0x22000 values (the `pmgrx` probe), other startup stores not in the stock audit, and anything iPadOS does after PMGR start and before AGX's first access (AGX's own sequence).
