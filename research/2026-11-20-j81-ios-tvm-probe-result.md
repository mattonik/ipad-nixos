# iPadOS +0x2d000 probe: result (2026-11-20)

Module `j81-ios-tvm-probe/checkra1n-kpf-pongo-j81-tvm` (sha256 9f84397c...), iPadOS 15.8.5 (19H394), temporary rootless palera1n boots. Plan: `2026-11-20-j81-ios-tvm-probe-plan.md`. Archive: `artifacts/live/private/gpu-offline/j81-tvm-device-c.logarchive` (the earlier `j81-tvm-device-incomplete-20261120-1058` was corrupt and is unused). Read only, no stores.

**Field relabel:** in these boots both `V1=` fields are PMGR region 0 +0x2d000 (not +0x32000, not +0x2300c).

| Boot UUID | local time | P0 V1 (+0x2d000, before GPC) | GPC TICKS | P1 F (page 5 x3) | P1 V1 (+0x2d000, after page 5, before core read) | CORE |
| --- | --- | --- | --- | --- | --- | --- |
| 6460BE8A-7BEB-477A-B35F-15CA7226B745 | 10:49:04.885 | 0x00000001 | 0x3990 | 40000000 x3 | 0x00000001 | 0x00070500 |
| 9DCD022A-6CAF-479D-9EC7-CE527CEF9452 | 11:02:02.755 | 0x00000001 | 0x3924 | 40000000 x3 | 0x00000001 | 0x00070500 |

(The 10:49 boot is the first attempt that ended with the iPad back on iPadOS; the probe had fired there, the collect of it was the corrupt archive.) Other fields as before: S=0x300, P=0x80000000 then 0x80110100, V0=1.

## Comparison with Linux (`2026-11-20-j81-linux-tvm-snapshot-result.md`, boot 8e26e203)
| Phase | iPadOS | Linux |
| --- | --- | --- |
| before GPC (Linux B2, with MiscACG store) | 1 | 0 |
| after page 5 high | 1 | 0 |

Phase-matched: iPadOS has the SoC TVM control (+0x2d000) at 1 before the GPC request and after page 5 rises; Linux has 0 at both, with MiscACG written to 1 and page 5 high. Bit 0 is the stock request old|1 for soc-tvm (group 3, rail 1, no enable poll).

## Reading
The missing-enable hypothesis survives and is now a concrete phase-matched difference: the one register compared so far where the working iPadOS boot differs from Linux while the GPU-ID read hangs only on Linux. Still a correlation on one device (two boots): it does not show the control gates the core window, and the 0 on Linux could be a state rather than an unset request. Not tested: any Linux write of +0x2d000, status +0x2d100, CPU TVM, DPE.
Next candidate step (needs a plan and approval, not prepared): on Linux, a guarded one-time store of old|1 to +0x2d000 (as done for MiscACG), then read back, then the existing core-ID read with the watchdog. A write to a rail-related control, so it needs its own go-ahead.
