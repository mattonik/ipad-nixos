# Mapping-only observation: result (2026-11-20, boot caacf910-35b5-40cf-b597-ded25ca1d769)

Plan: `2026-11-20-j81-map-probe-plan.md`. Fresh observer boot, observer kernel (notes a2dda271...), module `j81-map-walk.ko` (e441f354...) and probe (48451432...). The probe mapped three pages through /dev/mem exactly as the core-ID reader does (O_RDONLY|O_SYNC, length 0x1000, PROT_READ, MAP_SHARED) and never dereferenced them. No device register was read or written. rc=0.

| Mapping | VA | Leaf | PTE | Output PA | AttrIdx -> MAIR byte | SH | AP | AF | nG | PXN | UXN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| page 5 | 0xffff9a613000 | pte, 4 KiB | 0x16000020e005fcf | 0x20e005000 | 3 -> 0x00 | 3 | 3 | 1 | 1 | 1 | 1 |
| GPC state | 0xffff9a612000 | pte, 4 KiB | 0x160000201e01fcf | 0x201e01000 | 3 -> 0x00 | 3 | 3 | 1 | 1 | 1 | 1 |
| core | 0xffff9a611000 | pte, 4 KiB | 0x160000201000fcf | 0x201000000 | 3 -> 0x00 | 3 | 3 | 1 | 1 | 1 | 1 |

Common: MAIR_EL1 0x000000040044ffff (byte 3 = 0x00, Device-nGnRnE), TCR_EL1 0x00000021b5503510, vm_flags 0x40444d1 (io, pfnmap, read, shared), vm_page_prot 0x60000000000fcf, same upper-level entries (pgd 0x800000808923403, pud 0x800000805363403, pmd 0x8000008089f0403). The three PTEs differ only in the output address.

## Reading
The core page is mapped as expected: correct PA (0x201000000, 4 KiB), peripheral memory type (MAIR byte 0x00, the packet's expected value), identical attributes to the two pages that read successfully before (page 5 and GPC state). So the CPU translation of the core aperture, on the Linux side, is not the difference: a read through this mapping reaches the bus at the right address with the right type. This agrees with the static audits (same address, width, ordering as the iPadOS reader).
Not done: the iPadOS-side runtime mapping was never captured (no archive has one), so an iPadOS attribute difference can't be excluded, but the Linux mapping already has no anomaly. Attention moves to what the hardware does behind that access: clock/reset/Fender state, CPU TVM (0x202220048), DPE throttle, other PMGR start stores not yet compared, and the page-1/page-4 words.

Raw: `artifacts/live/private/j81-map-probe-results-20261120-run1/` (git-ignored).
