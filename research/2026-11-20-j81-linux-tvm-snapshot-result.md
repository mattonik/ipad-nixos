# Linux +0x2d000 snapshot run: result (2026-11-20, boot 8e26e203-8a8d-49fb-b7f2-f45bd19ec821)

One boot, campaign rc=0, no watchdog event, no core-ID access. Plan: `2026-11-20-j81-linux-tvm-snapshot-plan.md`.

| Snapshot | PMGR +0x2d000 | MiscACG +0x32000 | page 5 +4 | perf +0x1c200 | +0x2300c |
| --- | --- | --- | --- | --- | --- |
| A | 0x00000000 | 0 | 0 | 0x80000000 | 0 |
| B (before MiscACG store) | 0x00000000 | 0 | 0 | 0x80000000 | 0 |
| B2 (after store, before GPC) | 0x00000000 | 1 | 0 | 0x80000000 | 0 |
| C (after page 5 high) | 0x00000000 | 1 | 0x40000000 | 0x80110100 | 0x164 |

Other words unchanged (GFX PS 0x3ff, +0x1008 0x80480348, +0x4008 0x88480348). GPC poll raw 0x1 after 11 polls; page-5 bit 30 high on both samples (first under 1083 ns after the poll, later under 101916 ns). Same page-5 result as the three earlier MiscACG-write boots.

Reading: on Linux the SoC TVM control stays 0 through the whole page-5-high sequence, so Linux never sets it. This is consistent with the missing-enable idea, but it does not test it: the working iPadOS value at the same phase is still unknown. The next piece is that iPadOS counterpart (probe reading +0x2d000 before the core read, same phase as the P1 record). Not prepared.

Raw: `artifacts/live/private/j81-linux-tvm-snapshot-results-20261120-run1/` (git-ignored).
