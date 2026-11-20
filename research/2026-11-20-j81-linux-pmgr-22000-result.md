# Linux PMGR +0x22000 read: result (2026-11-20, boot 83536afb-ea75-4b65-bb54-e5de82a422e2)

Fresh observer boot, read-only (`boot/j81_linux_pmgr_words.py`, pinned pmgr-words-peek, 256 words +0x22000..+0x223fc in 4 chunks, no GFX power-on, no stores). Raw: `artifacts/live/private/j81-linux-pmgr-words-20261120-run1/` (words.txt, chunk logs).

| Word | Linux (fresh boot, nothing written) | iPadOS (before and after GPC, `...-ios-fender-pmgrx-cpu48-result.md`) |
| --- | --- | --- |
| +0x22000 | **0x00000000** | **0x80000000** |

So +0x22000 is a real difference: bit 31 is set on iPadOS before the GPC request and clear on Linux. Other words of this block already have bit 31 set on Linux without any write from us: +0x22010, +0x22020, +0x22080 = 0x80000000 and 11 more 16-byte-aligned words (+0x220c0, 0x220d0, 0x220e0, 0x220f0, 0x22100, 0x22110, 0x22140, 0x22150, 0x22160, ... 14 in total in the 256-word window; 61 nonzero words overall). Those match the A8 thread's description of per-domain bit-31 words (set by the bootloader on Linux), while the +0x22000 one is the exception here. The iPadOS values of the other 0x220xx words were not read (the probe has only +0x22000), so only this one word is compared.

What +0x22000 is: not one of the six `ps-regs` blocks in the J81 ADT (those are 0x20000, 0x20100, 0x20200, 0x20300, 0x20400, 0x21000), so it is not a power-state register; the stock method that sets it was not located in this session (the A8 thread says ApplePMGR::start does `0x20e022000 |= bit 31`, which fits the iPadOS value but is unverified for T7001 here).

## Reading
After the CPU/Fender exclusions, +0x22000 bit 31 is the next concrete unmatched difference between working iPadOS and hanging Linux (the others, MiscACG, +0x2d000, the page-1/page-4 pair, are already matched by the Linux tests and still hang). It is one word on one device; the T7000 report calls the write not needed there. Not prepared: a guarded Linux store (old must read 0x00000000, new 0x80000000 = old|bit31, readback must match) in Apple's order with the others before GFX power-on. It would follow the same pattern as the previous writers, but what the bit does is unknown, so it needs your go-ahead; the stock method that sets it should first be located in the 19H394 kernel (offline) so the write matches Apple's transform and caller.
