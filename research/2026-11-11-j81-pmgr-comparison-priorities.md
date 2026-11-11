# J81 PMGR comparison: what is known and what to measure next

Offline review of the November 11 Linux captures and prior iPadOS/LLB
analysis. No new device access. Linux and iPadOS samples below were obtained
on different boots and at different points; they are not atomic snapshots.

## Existing cross-system comparisons

| PMGR region-0 offset | Linux | iPadOS 19H394 | Qualification |
| --- | --- | --- | --- |
| `0x5000` | `0x00001010` | `0x00001010` | Baseline Linux, iOS after identity; post-GPC Linux also observed the same value |
| `0x5004` | `0x00000000` | `0x40000000` | Linux immediately after GPC poll, iOS sampled after GPC poll; bit 30 remains unexplained |
| `0x5008` | `0x81480348` | `0x81480348` | Separate baseline/identity boots; post-GPC Linux also saw that value |
| `0x1c200` | `0x80000000` then `0x80110100` | `0x80000000` then `0x80110100` | Selected before/after GPC points |
| `0x1c010`, `0x1c014` | `0x6436d063`, `0x00000070` | same | Two GFX table words only |
| `0x23000` | `0x00000001` | `0x00000001` | Different boot points |

The existing [page-5 LLB data-flow analysis](2026-11-09-j81-llb-page5-clock-dataflow.md)
shows that software calculates a rate from that page, but did not establish
that it is the GPU PLL or directly feeds GFX. The known GFX performance table
has a separate path. Calling `0x5000` the GPU PLL, or assuming bit 30 controls
GPU readiness, would exceed the evidence.

## Additional voltage-control clue

The Linux after-GPC PMGR sampler recorded `0xbb81ac05` at each of `0x23014`,
`0x23018`, `0x2301c`, and `0x23020`. The private static 15.8.8 LLB
decompilation `ghidra-iboot/dec_15llb_dwi.c` and instruction-derived MMIO
inventory `mmio_15llb.txt` show one conditional LLB path writes that same
constant to those four addresses. This is a reproducible connection between
Linux's observed words and a bootloader setup pattern, not a live iPadOS
comparison: the analyzed LLB is 19H422, the instrumented iPadOS is 19H394,
and static presence does not prove the path ran. The electrical meaning of
these words and their relationship to GPU voltage are not established.

Linux also recorded `0x23004=0x170`, `0x23008=0`, `0x2300c=0x164`, and
`0x23010=0x16d`. Earlier static work connects an iOS 8.1 CPU-performance
controller path to `0x23004`, but does not establish its units or a GFX
dependency. No equivalent 19H394 runtime values have been found in the
existing instrumented logs. No register writes are justified by this.

## Next decision

1. Establish which GFX provider or hardware path actually selects the
   clock/voltage, and trace its inputs or reads in the matching 19H394
   kernel. Prioritize an address with a concrete pre-identity GPU dependency
   over a broad sweep of unnamed PMGR words.
2. If that static work identifies a discriminator, adapt the existing
   one-read iOS framework to sample a small, fixed set at justified points;
   check each method's mapping and read side effects, and compare with a
   correspondingly timed Linux capture. A completed read is not proof of
   absence of side effects. Read-only MMIO can stall or reset the device.
3. Treat the two populated DWI configuration words as observations, not
   proof of the whole DWI setup or protocol. The current evidence links DWI
   to backlight control, not specifically GPU rail control; see the
   [DWI review](2026-11-11-j81-claude-dwi-review.md).

Sources: `artifacts/live/gpu/pmgr-words-20261111-after-gpc1/{plls,volman}.log`,
the prior [page-5 results](2026-11-10-j81-page5-capture-results.md), and
PR #38's iPadOS performance-control and table captures. Raw device logs and
Apple binaries remain private.
