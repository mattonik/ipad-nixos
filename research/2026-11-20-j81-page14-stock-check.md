# Stock-kernel check of the page-1 / page-4 +8 writes, and the iPadOS readback (2026-11-20)

Answers `to-builder/2026-11-19-j81-clock-pages-dd0246b` (REVISION dd0246bb243a81bbe7956ef59fc18d90f9ac7619). Host verifier `verify-host.sh` ran clean on this Mac (all SHA-256 OK; audits PASS: high-pair/rate-select/bypass/zero-divisor test, pmgr-words-peek test, original opcodes + 636 selector pairs with slot 2 = 6, slot 5 = 196, slot 6 = 0 entries, 52 native rate cases and 131072 native writer checks; the six computed rates 24, 798, 24, 100, 2400, 0 MHz match the ADT clock column). No device was needed.

## What the stock writes do (19H394, from the packet's note and audit, reproduced)
- The T7001 method at `0xfffffff006c8872c` reads +0x1008, computes `(old & 0x3fffffff) | 0x40000000`, writes it to the same offset, then does the same at +0x4008, then calls its parent at `0xfffffff006c8879c`. Unconditional on that path; it never tests its readback and never touches page 5. It can be reached from startup and from the platform "active" action early in wake.
- It changes only bits 31:30 (10 -> 01 starting from the Linux value); the low 30 bits (multiplier, divider, bypass fields) are preserved.
- **Effect on the clock software:** none visible. The J81 19H422 LLB rate calculation does not consume +8[31:30]; page 1 stays 798 MHz and page 4 2,400 MHz whichever of the 16 high-pair combinations is used (the audit varies all of them). The stock kernel's only named PLL4 consumer (`_pll4Frequency` at object +0x35040, ISP reference clock getter) reads a cached value, none of the three MMIO words. So the written change does not alter the published rate; its **electrical function is unresolved**: no source here says what [31:30] on +8 does (a different stock method, `setPLLOffMode`, programs a high pair at `(index<<14)|4`, not at these offsets).
- It does not explain the page-5 rise: Linux already has +4 bit 30 set on pages 1 and 4 and page 5 rises on Linux with the pair still 10 (all four MiscACG boots), so a page-local "01 => bit 30" rule fails and the pair is not needed for page 5.

## Working rows vs failing rows (archive question of the packet, now with a real readback)
| Role | Source | Boot / provenance | +0x1008 | +0x4008 | Phase |
| --- | --- | --- | --- | --- | --- |
| working (core ID 0x00070500) | iPadOS 19H394, `page14` probe, `gpu-offline/j81-page14-device.logarchive` | DB520358-..., 12:30:36.062 (P0) and .063 (P1) | 0x40480348 | 0x48480348 | before GPC (P0) and after GPC + page 5 high, before the core read (P1): identical |
| failing (core read hangs) | Linux observer boots 8e26e203, f1fffd5d, 3e69fa2d, ... (`from-builder/2026-11-20-*`) | snapshots A/B/B2/B3/C | 0x80480348 | 0x88480348 | every phase, with and without MiscACG and +0x2d000 |
Archive coverage: `ios-logarchive-j81-pmgr-bisect-03/kernel.log` (14 Nov, 240 MB) contains the seven recipe markers but no readback of either word (searched `J81_BOOT`, the two physical addresses, all four full words); `j81-ios-pmgr-store-slice` and `...power-store-sample` carry only the staged-store rows. So the new `page14` boot is the first retained iPadOS readback, and the earlier "requested" values (0x40480348 / 0x48480348) now have a matching observed state.

## Decision per the packet
Working = 01/01 and failing = 10/10 at aligned phases, so this is flagged as an **association**, the strongest unmatched one left on J81. It does not separate page 1 from page 4 (both differ), nor from other startup state, and it is one working boot. Linux can reproduce it with an ordinary read-modify-write of each word.

## If a Linux write test is prepared (not prepared)
Risk class: PLL configuration words (page 4 is the 2.4 GHz one) rather than an enable bit. Mitigations that follow from the check: replicate Apple's exact transform `(old & 0x3fffffff) | 0x40000000`, only if the word reads exactly the Linux value (0x80480348 / 0x88480348) so it is Apple's own transition from the same starting state; write page 1 and page 4 separately with a snapshot between and a readback; software-computed rates do not change; keep the 20 s watchdog on the core read; stop if a readback differs from the request. The first write on a live clock tree could still glitch something the notes cannot rule out (m1n1/Linux may use PLL pages), so it needs the go-ahead.

Remaining unknown: what +8[31:30] controls electrically, and whether it matters for the core window (on T7000 the same write was reported "not needed"); the CPU TVM/DPE words (`cpu48`, `cpu194` probes) are still unmeasured.
