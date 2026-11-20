# Linux MCC-bank replay in Apple's order: result (2026-11-20, run 3, boot 36e22c25-f6ec-4025-be13-00dc24f6b165)

Plan: `2026-11-20-j81-boot-path-diff-review.md`; runs 1-2 are `2026-11-20-j81-linux-mcc-write-run1-stopped.md` (run 1 stopped by my too-strict bit-30 check before GFX power-on; run 2 was the old boot and refused at its first check). Run 3 is a fresh DFU boot, one shot. Order, all before GFX power-on: PLL1 +0x1008, PLL4 +0x4008, MCC bank (+0x22000, +0x22090, +0x220a0, +0x220b0, +0x22130, stock transform), MiscACG, voltage-manager check, SoC TVM; then GFX cycle, bridge plan, GPC batch, gated core-ID read under the 20 s watchdog.

| Snapshot | GFX PS | +0x1008 | +0x4008 | +0x22000 | +0x22090 | +0x220a0 | +0x220b0 | +0x22130 | MiscACG | +0x2d000 | page 5 +4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S0 | 0x300 | 0x80480348 | 0x88480348 | 0 | 0x09070300 | 0x09040300 | 0x09060300 | 0x09040300 | 0 | 0 | 0 |
| S1 (PLL1) | 0x300 | **0x40480348** | same | same | same | same | same | same | 0 | 0 | 0 |
| S2 (PLL4) | 0x300 | same | **0x48480348** | same | same | same | same | same | 0 | 0 | 0 |
| S3 (MCC) | 0x300 | same | same | **0x80000000** | **0x89070300** | **0x89040300** | **0x89060300** | **0xc9040300** | 0 | 0 | 0 |
| S4 (MiscACG) | 0x300 | same | same | same | same | same | same | same | **1** | 0 | 0 |
| S5 (TVM) | 0x300 | same | same | same | same | same | same | same | 1 | **1** | 0 |
| A (GFX cycle) | 0x3ff | same | same | same | same | same | same | same | 1 | 1 | 0 |
| B (bridge) | 0x3ff | same | same | same | same | same | same | same | 1 | 1 | 0 |
| C (GPC) | 0x3ff | same | same | same | same | same | same | same | 1 | 1 | **0x40000000** |

All writes (PLL1, PLL4, five MCC words, MiscACG, TVM) succeeded with the exact expected immediate readbacks and persisted through the GFX cycle, the bridge plan and the GPC batch; as in run 1, +0x22130 gained bit 30 (status) after the enable (0xc9040300), the other four MCC words stayed as requested. GPC poll raw 1 after 11 polls; page-5 bit 30 high on both samples; vm_sram 0x170/0x180. Then the gated core-ID read: GFX PS, MiscACG, page 5, GPC state and control all read and fed, `stage=before-gpu-revision address=0x201000020` and **no result**: hang, watchdog reset, iPad back on iPadOS.

## Reading
Linux now matches the working iPadOS boot on every register we have been able to compare (PLL1/PLL4 words, the MCC enable bank, MiscACG, SoC TVM and status, voltage manager, vm_sram, page 5, GPC, perf, +0x2300c, Fender, the page mapping), in Apple's order, before GFX power-on, and the core read still hangs. The five-word MCC difference was real but is not what blocks the core window. What remains unmeasured or unmatched: the DPE words and any other iBoot/early-kernel write outside the sampled registers (see `from-builder/2026-11-20-j81-boot-path-diff-result/startup-inventory.md` and `bootloader-inventory.md`), registers outside PMGR region 0 (CPU cluster block, AMCC/fabric, the GPU block's own state), and whatever the GFX power-on and bridge/GPC sequence needs to see that Linux cannot observe. Sequence timing differs too: our stores run seconds apart over the USB console, Apple's microseconds apart.
