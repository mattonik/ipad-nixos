# iPadOS Fender +0, PMGR extras and CPU TVM: result (2026-11-20)

Probe `j81-ios-state-probes/checkra1n-kpf-pongo-j81-fender-pmgrx-cpu48` (13 patched words, runbook step 2), iPadOS 15.8.5 (19H394), temporary rootless palera1n boot, boot UUID B6FF1EED-124B-4BEB-9C17-E1B2A8115487, local 13:51:32. Read-only. Archive `artifacts/live/private/gpu-offline/j81-fender-pmgrx-cpu48-device.logarchive`; decoded by `boot/decode_j81_ios_probe.py`.

| record | S (GFX PS) | page 5 +4 | +0x2d100 | vm_sram 0x23004 | +0x22000 | Fender +0 (G) | CORE field |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 (before GPC) | 0x300 | 0 | 0x00000001 | 0x170 | **0x80000000** | n/a | n/a |
| GPC TICKS | 0x3947 | | | | | | |
| P1 (after GPC, page 5 high) | | 0x40000000 x3 | 0x00000001 | 0x170 | **0x80000000** | **0x40000000** | CPU cluster 0x202220048 low word = **0x00000000** |

(In this boot `CORE=` is the CPU TVM word, not the GPU ID; the GPU ID was not read.)

## Comparison with Linux
| Item | iPadOS | Linux (2026-11-20 runs) | Verdict |
| --- | --- | --- | --- |
| Fender +0 before the ID read | 0x40000000, bit 29 clear | 0x40000000, bit 29 clear (boots 49df36fd and later; wake logs 2026-11-06) | same: the Fender bit-29 hypothesis is excluded at this point |
| +0x2d100 (soc-tvm status) | 1 before and after GPC | 0 before the +0x2d000 store, 1 after it | same once +0x2d000 is set |
| vm_sram 0x23004 | 0x170 | 0x170 (0x180 transient) | same |
| CPU TVM 0x202220048 bit 0 | **0** (low word 0x00000000) | not measured | iPadOS does not have this bit set at this phase: not a candidate for Linux to copy |
| +0x22000 | **0x80000000** | **never read on Linux** | unmeasured on Linux: next cheap check |

## Reading
Two candidates fall: Fender bit 29 (clear on iPadOS, like Linux) and CPU TVM bit 0 (clear on iPadOS). The stock audit says cpu-tvm requests old|1 at 0x202220048, but the word reads 0 at the end of `ApplePMGR::start()` on this boot, so either that path does not run for J81 at this point or the bit lives elsewhere; either way it is not what makes iPadOS differ. Open: +0x22000 bit 31 (iPadOS 0x80000000), the DPE words (cpu194 and the other CPU probes), the per-domain 0x220xx bit-31 words from the A8 thread's list, and anything between PMGR start and AGX's first access. Linux has not been compared at +0x22000 yet, a read-only check.
