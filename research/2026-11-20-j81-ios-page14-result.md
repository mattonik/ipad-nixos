# iPadOS page-1 / page-4 words, observed: result (2026-11-20)

Probe `j81-ios-state-probes/checkra1n-kpf-pongo-j81-page14` (see `2026-11-20-j81-ios-state-probes-plan.md`), iPadOS 15.8.5 (19H394), temporary rootless palera1n boot, boot UUID DB520358-... (local 12:30:36). Read-only. Archive `artifacts/live/private/gpu-offline/j81-page14-device.logarchive`.

**Field relabel for this probe only:** P0 `F=` is PMGR +0x1008, P0 `P=` is +0x4008 (before GPC). P1 `F=a/b/c`: a = +0x1008, b = +0x4008, c = page 5 +4 (after GPC and page 5). P0 `V1=` is +0x2300c as in the original module; `G=` is the log-buffer field (0x33303800 this boot, scratch).

| record | machTimestamp-order | value |
| --- | --- | --- |
| P0 | 12:30:36.062437 | S=0x300 (GFX off), **+0x1008 = 0x40480348, +0x4008 = 0x48480348**, V0 (+0x23000) = 1, V1 (+0x2300c) = 0 |
| GPC TICKS | 12:30:36.063144 | 0x391a |
| P1 | 12:30:36.063167 | **+0x1008 = 0x40480348, +0x4008 = 0x48480348**, page 5 +4 = 0x40000000, perf +0x1c200 = 0x80110100, V0 = 1, V1 (+0x2300c) = 0x164 |
| BEFORE CORE READ / CORE | .063193 / .063207 | CORE = 0x00070500 |

## Comparison with Linux (all Linux boots: +0x1008 = 0x80480348, +0x4008 = 0x88480348 in every snapshot, before and after page 5, with and without MiscACG/+0x2d000; `2026-11-19-j81-observer-paired-result.md` and the 2026-11-20 Linux results)
| word | iPadOS (read, both phases) | Linux (read, all phases) | difference |
| --- | --- | --- | --- |
| PMGR +0x1008 | 0x40480348 | 0x80480348 | bits 31:30: 01 vs 10 |
| PMGR +0x4008 | 0x48480348 | 0x88480348 | bits 31:30: 01 vs 10 |

The low 30 bits are identical; only bits 31:30 differ. This is an observed state, not a requested store: the first retained iPadOS readback of these words (the earlier packets had only Apple's requested values, 0x40480348 / 0x48480348, from another boot). It matches the A8 thread's "PLL1/PLL4 +8 [31:30] = 01" start write. The iPadOS value is already in place before the GPC request (P0), so it was set before the GFX/bridge/GPC sequence; Linux never sets it.

## Reading
This is the first register compared between the working iPadOS boot and the hanging Linux boots at matching phases that Linux has not been made to match: GFX PS, MiscACG, +0x2d000, page 5, GPC state/control, perf, +0x2300c, vm_sram, the mapping all match or are excluded; PLL1/PLL4 +8 [31:30] differ. A correlation on one device, one boot (the earlier iPadOS boots had no readback of these words). It does not show these bits gate the core window: on the T7000 report this write was bisected as "not needed", and whether it matters on T7001 is untested.
Next candidate (not prepared, needs your go-ahead): a Linux run in Apple's order that also sets [31:30] = 01 in +0x1008 and +0x4008 (read-modify-write, only if the word reads the Linux value), before GFX power-on, with MiscACG and +0x2d000 as in the last run, then the gated core read. This writes PLL control words, a riskier class than the earlier PMGR enables: first confirm from the stock kernel what these two writes do (the clock-word notes in the mailbox packet) and what the bits mean for the bus clock.
