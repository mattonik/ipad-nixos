# iPadOS CPU cluster +0x20 and Fender (probe `fender-cpu20`): result (2026-11-20)

Probe `j81-ios-state-probes/checkra1n-kpf-pongo-j81-fender-cpu20` (5 patched words), iPadOS 15.8.5 (19H394), temporary rootless palera1n boot, boot UUID 54A9E804-A8B9-416A-A78C-0108E354E641, local 15:25:13. Read-only. Archive `artifacts/live/private/gpu-offline/j81-fender-cpu20-device.logarchive`, decoded by `boot/decode_j81_ios_probe.py`. (Two earlier attempts stalled at "Booting PongoOS" and produced no archive.)

| record | value |
| --- | --- |
| P0 (before GPC) | S 0x300, page 5 0, perf 0x80000000, 0x23000 = 1, 0x2300c = 0 |
| GPC TICKS | 0x3941 |
| P1 (after GPC) | page 5 0x40000000 x3, perf 0x80110100, 0x23000 = 1, 0x2300c = 0x164 |
| P1 `G=` Fender +0 (original mapping, read just before the core read) | **0x40000000** (bit 29 clear, bit 30 set) |
| `CORE=` (in this variant: CPU cluster 0x202220020 low word) | **0x00000000** |

## Reading
- Fender +0 = 0x40000000 again, second independent boot (first: B6FF1EED); matches Linux.
- The CPU cluster word +0x20 reads 0 on iPadOS at the end of ApplePMGR::start. The stock path would request `(old & 0xffffffff9ff88fff) | 0x60002000` there (bits 29, 30, 13 set) if it executed; the word reads without them. Together with CPU TVM (+0x48 bit 0 also 0 on iPadOS) the resource at 0x202220000 reads all-zero in the two words sampled, so either those CPU-side writes are conditional and did not run on this path, or this mapping returns zeros (no positive control yet). To tell which, one word that the stock path writes unconditionally with a nonzero value is needed: the DPE calibration words (+0x1b0, +0x1a0, +0x150, +0x190) are the candidates (probes `fender-cpu1b0`, `fender-cpu1a0`, `fender-cpu150`, `fender-cpu190`, `fender-cpu194` are ready).
- Not a difference to copy to Linux: with CPU +0x20 and +0x48 both zero on iPadOS, there is nothing nonzero here that Linux lacks.
