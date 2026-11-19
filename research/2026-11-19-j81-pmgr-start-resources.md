# J81 ApplePMGR startup before the early working core read

The mystery 64-bit accesses in ApplePMGR startup slot `+0x5c8` resolve to the **CPU cluster performance controller**. The logical selector is 8, the provider memory index is 1, and the corresponding physical base in the J81AP 19H394 restore tree is `0x202220000`. This resolves a mapping left open in the [earlier GFX comparison](2026-11-18-j81-gfx-state-word-comparison.md#test-necessity-against-the-earlier-successful-boot). The early iPadOS recipe returned `0x00070500` after PMGR startup. Its log establishes that the recipe could work in that context. It did not measure this CPU block or identify which startup operation made the GPU accessible. [Working boot](2026-11-14-j81-ios-boot-bisect-probe1-results.md)

## How the mapping closes

Addresses below are unslid, with the common prefix `0xfffffff00` omitted. Inputs are the exact decompressed 19H394 kernel and J81AP tree identified by SHA-256 in the [register comparison](2026-11-18-j81-gfx-state-word-comparison.md).

| Stage on the inspected startup path | Evidence |
| --- | --- |
| Install logical mappings | At `6bb97d0` start calls slot +0x588. The reviewed T7001 table at `6fe69c0` resolves it to `6c88488`. The method first requests selector 0 / resource 0, then selector 8 / resource 1. Both use instance 0. |
| Acquire the provider resource | The common thunk at `6c8ae44` resolves through `6fe5d38` to `6bbf5d0`. On the instance-zero path, `6bbf6fc` saves the supplied resource index. At `6bbf714` the provider receives that index and options zero. The IOService vtable slot resolves to the named `mapDeviceMemoryWithIndex` method. |
| Retain its address | At `6bbf73c` the IOMemoryMap slot resolves to `getVirtualAddress`. The result is stored at `this + 0xa70 + 0x50 * selector`. The lookup helper at `6bc75e4` returns the corresponding descriptor at `this + 0xa58 + 0x50 * selector + 0x28 * instance`. Its +0x18 field is exactly the mapped address. |
| Use that mapping | Startup call `6bb9824` goes through +0x5c8 to `6c8872c`. After ordinary region-0 work at +0x1008 and +0x4008 and a parent call, its 64-bit helpers use descriptor 8, instance 0. The load at `6bcf830` and store at `6bcf8a0` both use the mapped base. |
| Translate to the stock board | PMGR reg[1] has child base `0x02220000`, length `0x2000`. The arm-io range adds `0x200000000`. All three eight-byte accesses fit. The independent T7001 Linux DTS names the overlapping first 4 KiB as the CPU performance controller. |

XNU's implementation indexes the provider device-memory array. The physical-address conclusion assumes that the provider exposes the restore tree's resource ordering on this path. The published early boot has no runtime map dump. [Apple IOService](https://github.com/apple-oss-distributions/xnu/blob/xnu-8019.41.5/iokit/Kernel/IOService.cpp) · [T7001 Linux DTS](https://gbmc.googlesource.com/linux/+/f79749a8e42b3a6dcb980e87f3ef752962b9f094/arch/arm64/boot/dts/apple/t7001.dtsi)

## What startup changes and where it could matter

* At `6c887a0..6c887e4`, the routine copies bits 63:56 from CPU controller +0x78 into +0x68, preserving the lower 56 bits at +0x68. These are the state-2 and state-0 entries of the CPU performance-state table.
* At `6c887e8..6c88824`, the requested 64-bit value at +0x20 is `(old & 0xffffffff9ff88fff) | 0x60002000`. Its desired CPU state field at bits 24:22 is preserved.
* The J81 voltage-manager enable method at `6c8a164` is slot +0x698. It clears bits 11:8 at ordinary PMGR +0x23000, then takes the desired state from CPU controller +0x20. It requests the top byte of the corresponding +0x68 table entry at PMGR +0x23010 and a byte from the separate packed +0x110 table at PMGR +0x23004. The call at `6bcd100` passes enable=1. Its presence alone does not establish when that call ran in the successful boot. [Earlier voltage-manager analysis](2026-11-14-j81-ios-voltage-manager-enable.md)

The top-byte copy can change that particular CPU seed only if the seed lookup sees **state 0** after the copy and the original high bytes differed. For desired states 1–7 it reads a different entry. The SRAM lookup uses a different table, and this sequence has no direct store to the GFX code at +0x2300c. This is a narrow reason to rank the table copy below startup differences that directly discriminate the working GPU case. It leaves possible hardware side effects of the CPU control word open.

The project's pinned m1n1 independently locates the state table at cluster base `0x202200000` + `0x20068`. Its T7001 configuration requests state 2 before feature setup and state 7 at the end. This is bootloader policy; a saved CPU frequency or a later Linux voltage sample cannot establish the desired state when Apple read +0x20. [Pinned m1n1](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/cpufreq.c)

## Decision for GPU bring-up

Keep the in-progress early-recipe archive check first. If existing chronological evidence also gives the CPU desired state and seed values, apply the state-0 condition above. A matching CPU seed closes only this byte-copy hypothesis. A missing sample leaves it unresolved. The distinct GFX evidence is still the PMGR transition and the first appearance of page-5 bit 30 after the GPC request on the successful boot. There is no evidence here for replaying CPU controller writes or changing voltage settings on Linux.
