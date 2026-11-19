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
* The J81 voltage-manager enable method at `6c8a164` is slot +0x698. It clears bits 11:8 at ordinary PMGR +0x23000, then takes the desired state from CPU controller +0x20. It requests the top byte of the corresponding +0x68 table entry at PMGR +0x23010 and a byte from the separate packed +0x110 table at PMGR +0x23004. The parent dispatch below places that enable call before the state-table copy on this startup path. [Earlier voltage-manager analysis](2026-11-14-j81-ios-voltage-manager-enable.md)

### The parent call orders the MCC and voltage operations

At `6c8878c..6c8879c` the subclass loads the **parent** vtable through pointer `6fe5dc0`, then uses offset +0x5d8. The table pointer value is `6fcda40` and the entry at `6fce018` targets `6bccefc`. Inside this parent method, dispatches on the **instance** use the subclass implementations. Along the normal returning path, with intervening operations omitted, the order is:

1. The subclass has already requested region-0 +0x1008 and +0x4008.
2. The parent calls instance slot +0x688 with 1 at `6bccf3c`. On 19H394 this is `6c8a0c4`, the bit-31 read/modify/write loop over selected MCC/control-bank offsets in +0x22000..+0x22180. The exact loop starts at `6c8a0c4`. Nearby `6c8a01c` is a distinct method that looks up the MCC-related properties.
3. After further platform work, the parent calls +0x690 with 1, then +0x698 with 1 at `6bcd100`. The latter performs the voltage-manager enable and CPU/SRAM seed requests described above.
4. After the parent returns, the subclass copies the CPU state-2 high byte into state 0 and modifies the control word at CPU +0x20. The later tail dispatch at `6c8883c` is separate.

**The later table copy cannot supply the CPU byte used by the earlier seed in this invocation.** Even a later seed lookup could see a change from this copy only if its desired state were 0 and the original high bytes differed. States 1–7 read different entries. The SRAM seed uses the separate +0x110 table. This trace establishes software order and requested values. It does not measure posted-write completion, analog voltage, autonomous hardware reactions or which thread produced an archived row.

This provides one startup call chain with the same order as the first ordinary-store groups reported on November 17. It makes a PMGR initialization source for the groups concrete. The old global recorder did not capture the ordinary caller or thread, and this static match cannot establish their provenance. [Visible prefix and coverage](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md)

The project's pinned m1n1 independently locates the state table at cluster base `0x202200000` + `0x20068`. Its T7001 configuration requests state 2 before feature setup and state 7 at the end. This is bootloader policy; a saved CPU frequency or a later Linux voltage sample cannot establish the desired state when Apple read +0x20. [Pinned m1n1](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/cpufreq.c)

## A GFX-specific startup branch to distinguish

Between the MCC operation and voltage-manager enable, the parent reads byte `this+0xe4` at `6bccf40`. A zero selects `6bcd2c8` at `6bccf5c`; the other branch calls a different routine. The zero branch walks the enabled lanes of the `ps-regs` banks. At `6bcd458..6bcd46c` it maps the lane to a device ID and tests that device’s **software state** against 15. The J81 GFX record is ID 0x7c, bank 3, lane 4, with its enable bit set. For that record and instance 0 the state byte is at object offset `0x19094 + 0x7c = 0x19110`.

| State byte in this branch | What to look for in existing traces |
| --- | --- |
| 15 | Forward pass calls the minimum-state helper (record flag bit 2 clear), active setter and bridge dispatcher at `6bcd49c`, `6bcd4bc` and `6bcd4cc`. A setter may short-circuit depending on its own old word. |
| Below 15 | Forward pass skips this lane. In the reverse pass `6bcd538..6bcd558` calls the setter with that software state and auto disabled. |

This locates the previously identified replay routine **inside the startup path** and before voltage seeding. A captured GFX request with this caller would distinguish platform initialization from a later AGX provider invocation even with the same requested word. The boot’s eventual GFX hardware value of 0x300 supplies neither the earlier software byte nor its path selector. [Earlier replay observation](2026-11-04-j81-gpu-offline-trace.md#bridge-actions-and-already-active-pmgr-state-2026-11-05) · [GFX record and address lookup](2026-11-18-j81-gfx-state-word-comparison.md)

## Decision for GPU bring-up

Keep the in-progress early-recipe archive check first. If existing chronological evidence also gives the CPU desired state and seed values, apply the state-0 condition above. A matching CPU seed closes only this byte-copy hypothesis. A missing sample leaves it unresolved. The distinct GFX evidence is still the PMGR transition and the first appearance of page-5 bit 30 after the GPC request on the successful boot. There is no evidence here for replaying CPU controller writes or changing voltage settings on Linux.

The follow-up traced the software byte back to allocation. On the stock GFX record, both initializer seed flags are clear and no child propagates a request to GFX. The fresh-object prediction is a reverse request of zero. The November 14 successful-boot markers leave that prediction unmeasured. [Aggregate writer and archive check](2026-11-19-j81-gfx-startup-state-producer.md)
