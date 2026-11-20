# Review: agent result "provider slots +0x568/+0x570" (2026-11-20)

Source: from-builder/2026-11-20-j81-provider-slots-result (checksums OK).

- Slot +0x568 = clock/power request for GFX (ID 0x7c): requests active state 15 at 0x20e020320, on increase programs
  min/target/auto fields, polls ACTUAL, then applies 33 bridge pairs to each of two bridges (the 66 stores we replay).
  Slot +0x570 = status query (bit 8 / bit 9 of the same PS word) into caller stack; no extra GPU power/reset/QoS/SPR/SMC/SEP
  request found on the ordinary path. Fender path (+0x10000, +0, +0x1000, poll bit4, 10 us) runs on J81 with the values we replay.
- The iPadOS manual observer bypasses these callbacks and performs ONE activation: PS 0x300 -> request 0xf -> 0x3ff, then bridges, GPC, read.
- Every Linux run archived (10 results, linux-setter-archives.tsv) shows THREE requests: 0xf, 0xf0, 0xf (on, off, on; the
  deliberate get/put/get cycle from the 2026-11-06 PMGR-cycle experiment). No Linux run has a single activation.
  The 11-06 note only ruled out "the cycle alone"; single activation combined with today's state set (MiscACG, TVM, MCC bank, PLL, order)
  was never tried. Agent rank 1.
- Also: auto_word 0x100000ff on both active requests vs stock min/target/auto handling (native path would use 0x0, 0xf, 0x1000000f
  under the agent's assumptions); the iPadOS observer's actual auto write is not printed.
Next: Linux run with a single GFX activation (no off/on cycle), everything else as mcc-write run 3.
