# Linux single-variable MiscACG write: result (2026-11-19, one boot, iPad Air 2 J81, observer kernel a2dda271...)

Boot c92665fd-5364-4349-a7df-b756575bb9b3 (fresh observer RAM boot, repo preflight GO). Plan and code: ../2026-11-19-j81-linux-miscacg-write-prepared/.
Sequence: GFX get/put/get cycle -> snapshot A -> bridge plan -> snapshot B -> guarded MiscACG store -> snapshot B2 -> paired GPC/page-5 batch -> snapshot C.

## Result: with MiscACG = 1 set before GPC, page-5 +4 bit 30 RISES on Linux (observer control without the write: 0 and 0)
| Snapshot | 0x32000 MiscACG | 0x20320 GFX PS | 0x1008 | 0x4008 | 0x1c200 perf | 0x2300c | 0x5004 page 5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A (after cycle) | 0 | 0x3ff | 0x80480348 | 0x88480348 | 0x80000000 | 0 | 0 |
| B (after bridge plan) | 0 | 0x3ff | same | same | 0x80000000 | 0 | 0 |
| B2 (after write) | 1 | 0x3ff | same | same | 0x80000000 | 0 | 0 |
| C (after GPC batch) | 1 | 0x3ff | same | same | 0x80110100 | 0x164 | 0x40000000 |
- Write step: `old=0x00000000` -> stored 1 -> `new=0x00000001` (miscacg-write.log). Only that one word was written; the guard allowed it because the pre-value was exactly 0.
- GPC raw 1 after 11 polls; paired page-5 samples: first 0x40000000 (<708 ns after the poll load), later 0x40000000 (<101625 ns). Same perf/VM transitions as iPadOS (0x80110100 / 0x164).
- Same-boot checks and the watchdog held (campaign completed without error; see results/summary.txt, kpoll.log).

## Compared with the controls
- Linux control (from-builder/2026-11-19-j81-observer-finished-ed70e35-result): identical sequence, MiscACG 0 throughout -> page 5 0 and 0.
- iPadOS (from-builder/2026-11-19-j81-ios-pregpc-miscacg-run-result): MiscACG 1 before GPC -> page 5 rises, core ID 0x00070500.
One variable (MiscACG bit 0 before the GPC request) flips the page-5 outcome on Linux from 0 to bit 30 set. This run did not read the RGX core ID (the campaign has no core read),
so whether the core now answers is not established. One boot, one run: not yet repeated.

