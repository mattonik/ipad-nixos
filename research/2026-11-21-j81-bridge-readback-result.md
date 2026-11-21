# J81 Linux bridge read-back: all 66 words retained, before and after GPC

2026-11-21, one shot, logs (private) `artifacts/live/private/j81-linux-bridgerb-results-20261121-run1/`. Plan:
[2026-11-21-j81-bridge-readback-plan.md](2026-11-21-j81-bridge-readback-plan.md). Module `0ed516c1...` (no-core control plus read-back).

## Result
- Campaign exit 0, watchdog disarmed, iPad still up. One GFX activation (`old=00000300 request=0000000f`). Both gates passed.
- Batch returned: GPC state 1 after 28 polls, last store to successful poll about 286 us, page 5 +4 = 0x40000000 (bit 30 set), core read disabled.
- Read-back of all 66 plan offsets (33 per bridge: +0x18 and the 32 words at +0x40000..0x4007c) in the same irq-off batch:
  rb1 (after the 66 stores) t0 33/33, t1 33/33; rb2 (after the GPC poll and page-5 sample) t0 33/33, t1 33/33 equal the plan. No differing word.
- None of the 126 reads (most never read before) hung.

## Reading
On Linux every bridge word we write is retained and readable, unchanged by the GPC request. That answers agent follow-up 2 for the Linux side: bridge retention is not what
differs between Linux and iPadOS at the point of the core read, provided iPadOS also holds these values (unsampled; the stock kernel wrote the same tuples, 66/66 matched
the writer capture, but no iPadOS read-back exists). Remaining: iPadOS-side read-back of the same words (needs the KPF probe build), and agent follow-up 3 (PS/MiscACG on both sides of the activation).
