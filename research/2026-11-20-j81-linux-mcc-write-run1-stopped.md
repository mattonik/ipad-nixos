# Linux MCC-bank replay, run 1: stopped by my own check before GFX power-on (2026-11-20, boot in `j81-linux-mcc-write-results-20261120-run1`)

Flow in Apple's order (`2026-11-20-j81-boot-path-diff-review.md`). Steps completed: snapshot S0 (all expected Linux values), PLL1 store, PLL4 store, MCC-bank store (five words, readback exact), then snapshot S3. The harness then **stopped itself** before the MiscACG store, the GFX cycle, the bridge plan, GPC and the core read: `post-MCC snapshot: word 0x022130 is 0xc9040300, expected 0x89040300`. No GPU access of any kind happened in this boot; the iPad stays on Linux with PLL1/PLL4 and the MCC words changed.

| Word | before (Linux) | right after the store (writer readback) | snapshot S3 (seconds later) |
| --- | --- | --- | --- |
| +0x22000 | 0x00000000 | 0x80000000 | 0x80000000 |
| +0x22090 | 0x09070300 | 0x89070300 | 0x89070300 |
| +0x220a0 | 0x09040300 | 0x89040300 | 0x89040300 |
| +0x220b0 | 0x09060300 | 0x89060300 | 0x89060300 |
| +0x22130 | 0x09040300 | 0x89040300 | **0xc9040300** |

PLL1 0x80480348 -> 0x40480348 and PLL4 0x88480348 -> 0x48480348 read back as requested (snapshots S1, S2).

## Reading
All five stores took effect. Bit 30 of +0x22130 appeared after the enable: 0xc9040300 is the same value other enabled words already carry on Linux (+0x220d0..+0x22110, +0x22140, +0x22160..0x22180 are all 0xc9040300), so bit 30 looks like a hardware status bit that rises once the bank accepts the enable. The check that stopped the run was too strict (it required the exact requested word); it is fixed to ignore bit 30 on these five words only, with a test for exactly this case. The stock iPadOS capture only holds the *requests* (0x89040300 for +0x22130), not the final state, so whether iPadOS shows 0xc9040300 there is unknown but likely.
Not a failure of the experiment's question: the core read was not reached. The campaign refuses to rerun on this boot (the PLL/MCC words are no longer the expected pre-values), so the test needs a fresh DFU boot.
