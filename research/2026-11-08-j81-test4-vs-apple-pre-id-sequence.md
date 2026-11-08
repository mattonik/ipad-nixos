# J81 test4 compared step by step with Apple's pre-ID sequence

Date: 2026-11-08. Offline comparison of the test4 transcripts
(`artifacts/live/gpu/*-20261107-test4.log`, private) and the test helper
source (`boot/gpu-core-revision-once.c`) against the iOS 15 G4G probe
(`2026-11-08-j81-ios15-g4g-pre-id-clock-power.md`) and the PMGR traces from
the same day. No device access.

## Result

Test4 reproduced every hardware step Apple's driver performs before the
first GPU ID read, with the same values and in the same order. The two
remaining differences are timing and what the boot chain leaves behind.

| # | Apple (iOS 15 G4G probe, `0x...322c`) | Test4 (2026-11-07, same boot) | Same? |
|---|---|---|---|
| 1 | Clock enable `clock-gates[0]` and power enable `power-gates[0]`, both device 124 (`0x7c`, GFX). On iOS 15 both reach ApplePMGR's state change to state 15 | `clock-cycle` test4: PMGR `0x20e020320` from `0x300` (state 0) to `0x3ff` (target and actual 15) | yes |
| 2 | Right after state 15: bridge selectors 9 then 10, 33 pairs each | `clock-table` test4: the same 66 stores in the same order | yes (format-0 writer) |
| 3 | GPC map (`reg` 1) with `has-kf` clear: `+0x10000 = 0xffff0000`, `+0 = 0x40000000`, `+0x1000 = 0x11` | `gpc-init` test4: the same three writes, same values, same order | yes |
| 4 | Poll `+0x1000` while bit 4 is set | One poll read returned `0x1` (bit 4 clear) | yes |
| 5 | 10 µs delay, set a software flag | Several seconds between helper processes | timing only |
| 6 | Readback: none | `postgpc` test4: GPC state `0x1`, control `0x40000000`, bridge `+0x18 = 0x80010004` | — |
| 7 | RGX map (`reg` 0): identity vtable `+0xa38` reads `+0x20`, then `+0x18` | `core-revision` test4: PMGR still `0x3ff`, GPC `0x1`/`0x40000000`, then a 32-bit read of `0x201000020`, which never returned | yes, same first access |

Apple steps that turned out to have no hardware effect, or not to apply to
GFX: the kdebug codes `0x2700c001/2`, the interrupt and lock bracketing, the
related-device branch (GFX has none), the `bcc56c` timing helper (a PMGR
counter read), and the SoC tuner (MCC performance mode only).

## Memory type of the read

`gpu-core-revision-once.c` maps `0x201000000` with
`open("/dev/mem", O_RDONLY | O_SYNC)` and `mmap(..., MAP_SHARED)`. On arm64
that is a non-cached device mapping (`pgprot_noncached`, Device-nGnRnE)
for an address outside system RAM. That is the strict device type Apple SoCs
expect for MMIO, the same class XNU uses for `mapDeviceMemoryWithIndex`
I/O mappings. This is from the kernel's documented `/dev/mem` behaviour; the
running kernel's page tables were not checked, and the exact XNU attribute
was not confirmed.

## What is left

1. **What iBoot or iBEC configures.** On a normal boot iOS starts after
   iBoot. Under checkm8 → PongoOS → m1n1 → Linux, any GFX, RGX or fabric
   setup that iBoot performs, or that a later iBoot stage performs only when
   it boots the kernel, may be missing. Apple's kernel driver would then
   rely on it without doing it itself. This fits all the static evidence
   above. The iBoot and iBEC images for iPad5,3 12B410 are encrypted, but
   their keys are public in the same source as the kernelcache key
   (`kernelcache-12b410-source`). Decrypting them and searching for GFX,
   SGX and `0x201xxxxxx` accesses is the next offline step.
2. **Timing.** Apple reads identity about 10 µs after the GPC poll. Test4
   read it seconds later from a new process. A GPU that drops back to a
   low-power state on its own after GPC init would explain the hang. The
   PMGR still read `0x3ff` with `auto=0` right before the read, which argues
   against it at the PMGR level, but nothing checked RGX-internal power.
3. **Unknown hardware ownership.** Linux's PMGR genpd and the
   `pd_ignore_unused`/`clk_ignore_unused` setup were not changed for these
   tests. No evidence links them to the hang.

No new hardware test is justified by this comparison. A single-process run
of steps 1–7 with a 10 µs gap would test item 2. That is a repeat of the
core-ID read, which the stop rules in
`2026-11-08-j81-next-mcc-experiment-decision.md` forbid until offline work
gives a concrete reason.
