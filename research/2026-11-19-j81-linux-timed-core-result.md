# Linux timed GPC request + immediate core-ID read after the MiscACG write: result (2026-11-19, one boot, J81, observer kernel a2dda271...)

Fresh observer RAM boot (repo preflight GO). Plan/code: ../2026-11-19-j81-linux-timed-core-prepared/. Boot id in results/boot-id.txt.

## Result: the core-ID read hung even about 2 us after the GPC poll succeeded. The watchdog reset the iPad.
Supervised log (results/timed-core.log), all READs acknowledged and fed:
| step | value |
| --- | --- |
| pmgr-read 0x20e020320 (GFX PS) | 0x000003ff |
| miscacg-read 0x20e032000 (set earlier in the boot by the guarded store, A/B = 0) | 0x00000001 |
| gpc-state 0x201e01000 before the request | 0x00000000 |
| timed sequence: GPC stores (+0x10000 <- 0xffff0000, +0 <- 0x40000000, +0x1000 <- 0x11), tight poll | state 1 reached after 0x455 (1109) reads |
| page 5 +4 0x20e005004, read right after the poll | 0x40000000 (bit 30 set) |
| ticks (24 MHz) from poll success to just before the core read | 0x2e = 46 ticks, about 1.9 us (includes the page-5 read and one pipe write) |
| core ID 0x201000020 | no `stage=after-timed-sequence`; silence; watchdog reset |
The partial summary (summary-before-timed.txt) was on disk first; no snapshot C or final summary exists because the device reset.

## Interpretation
Timing is not the missing piece: the core read hung about 2 us after the poll (iPadOS: tens of us), with MiscACG = 1, page 5 = 0x40000000 and GPC state 1 confirmed just before. With the earlier hang (seconds after GPC), the core window does not answer at either end of the timing range tried.
Another iPadOS pre-read step is missing. Comparison points left: the page-1/page-4 request words (0x40480348 / 0x48480348 on iPadOS vs 0x80480348 / 0x88480348 on Linux), other startup writes between enableACG and the first GPU access, and the remaining page-5 / 0x1c300 state. One boot; not repeated.
