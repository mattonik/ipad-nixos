# Linux +0x2d000 write test: result (2026-11-20, boot f1fffd5d-209a-42b2-978b-9618d9e667a6)

Plan: `2026-11-20-j81-linux-tvm-write-plan.md`. One boot, one shot.

| Snapshot | +0x2d000 | MiscACG | page 5 +4 | perf +0x1c200 | +0x2300c |
| --- | --- | --- | --- | --- | --- |
| A | 0 | 0 | 0 | 0x80000000 | 0 |
| B | 0 | 0 | 0 | 0x80000000 | 0 |
| B2 (after MiscACG store 0->1) | 0 | 1 | 0 | 0x80000000 | 0 |
| B3 (after +0x2d000 store 0->1, readback 1) | 1 | 1 | 0 | 0x80000000 | 0 |
| C (after paired GPC batch) | 1 | 1 | 0x40000000 | 0x80110100 | 0x164 |

Other words unchanged (GFX PS 0x3ff, +0x1008 0x80480348, +0x4008 0x88480348). GPC poll raw 1 after 11 polls; page-5 bit 30 high on both samples. Both guarded stores succeeded (old 0, new 1); B3 equalled B2 except +0x2d000.

Gated core-ID read (watchdog-supervised): GFX PS 0x3ff, MiscACG 1, page 5 0x40000000, GPC state 1, GPC control 0x40000000 all read and fed, then `stage=before-gpu-revision address=0x201000020` and **no result**: the read hung, the 20 s watchdog reset the iPad (it came back as iPadOS). Same failure as the late-read run (49df36fd) and the timed run (a076f20f).

## Reading
With +0x2d000 set to 1 and MiscACG 1 before GPC, Linux now matches iPadOS on every register compared so far (GFX PS, MiscACG, +0x2d000, page 5, GPC state, GPC control, perf, +0x2300c) and the core ID at 0x201000020 still hangs. So the soc-tvm control is not sufficient on its own for the core window; the earlier hypothesis that it was the missing step is contradicted for this recipe (one boot). It does not show the control is irrelevant. Remaining differences, none yet measured on iPadOS: CPU TVM (0x202220048), DPE throttle, +0x2d100 status, page-1/page-4 request words (iPadOS requests 0x40480348/0x48480348, Linux holds 0x80480348/0x88480348; no iPadOS readback exists), the CPU mapping of the aperture, and anything iPadOS does between enableACG and the first GPU access that has no register-level capture.

Raw: `artifacts/live/private/j81-linux-tvm-write-results-20261120-run1/` (git-ignored).
