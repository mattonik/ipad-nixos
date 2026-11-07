# J81 Apple core-map provenance versus Linux `/dev/mem`

Offline trace of the first G4G identity read after test4. No device access was
performed.

## Apple path

The G4G probe at `FUN_ffffff80032935a0` (`gpc-link.c`) reads the provider's
`reg` property and selects resource index 0 for RGX or 1 for GPC. In the
two-entry J81 `sgx` `reg` property, index 0 is `0x201000000` and index 1 is
`0x201e00000`; the source reconstruction and ADT cross-check are recorded in
`2026-11-04-j81-gpu-offline-trace.md`.

For the RGX choice, the probe obtains provider `+0x3c8(index, 0)`, calls the
returned object's `+0x70`, and stores the result in G4G field `+0xaf0`
(`param_1[0x15e]`). The later identity dispatch is concrete: G4G vtable
`+0x800` targets `FUN_ffffff80032933cc` (`ident.c`); that method calls
`+0x810`, whose G4G target `FUN_ffffff800328de68` loads the pointer from
`+0xaf0` and performs 32-bit loads at `+0x20`, then `+0x18`. Thus Apple does
not directly dereference a literal physical address in this function. It
dereferences the provider/map-produced pointer for `reg` index 0. The exact
returned pointer value and its page attributes are not available in the
offline artifacts.

The local kernelcache resolves these as actual methods, rather than only API matches. Its exported symbols identify `IOService::mapDeviceMemoryWithIndex` at `0xffffff80023b8c04` and `IOMemoryMap::getVirtualAddress` at `0xffffff80023e4640`. The former's disassembly calls the provider vtable slot `+0x3c0` for `getDeviceMemoryWithIndex(index)`, then dispatches the returned descriptor's `+0xe0` with the options argument. The latter simply returns the mapped virtual-address field at map-object `+0x28`. Together with G4G's matching virtual call offsets, this closes the provider and result-method identities in the kernelcache.

For the actual RGX request, both explicit arguments are zero: index 0 and map options 0. Local kernelcache disassembly of `IOMemoryDescriptor::map(0xffffff80023e4984)` shows it adds option bit 1 (`orr w21, w1, #1`, `kIOMapAnywhere`) and invokes `createMappingInTask` with `kernel_map`; it adds no cache-mode override. `IOGeneralMemoryDescriptor::doMap` at `0xffffff80023e1be0` sees selector bits `(options >> 8) & 7 == 0` and creates the `IOMemoryReference`; that zero selector alone does **not** establish the eventual memory type.

The first-reference constructor is an internal helper at `0xffffff80023dda78`. Its decompilation shows that for a physical descriptor whose descriptor cache-mode field is still zero, it gets the first physical segment, calls `0xffffff80020c45dc` with the PFN, converts the returned cache attributes into the descriptor's cache-mode field, and uses that mode to configure the device pager. The helper at `0xffffff80020c45dc` returns `7` when the PFN is outside the runtime physical-memory range it checks; otherwise it reads a runtime per-page cache-attribute table (or returns `2` for a second range form). The saved J81 m1n1 run records DRAM at `0x800000000` with size `0x80000000` ([run record](../docs/software-only-control.md#attempt-4-same-round-both-fixes-together-recorded-on-video-the-cpu-check-now-passes-cleanly)); the RGX PA `0x201000000` is below the DRAM base. The cache helper uses runtime range globals in the kernel; the saved platform DRAM bounds support that this PA is outside the range, though those Apple globals were not captured during the mapping. On that basis, the helper takes the `7` fallback for this PFN. In the constructor's conversion, attribute `7` selects descriptor mode `4`, `kIOWriteCombineCache`. Its static mode-to-device-pager table maps mode 4 to flags `6` (`DEVICE_PAGER_CACHE_INHIB | DEVICE_PAGER_COHERENT`). Thus the resulting IOKit descriptor/pager mode is no longer an unknown: the request selector is default/zero, and its physical-page default resolves to write-combine mode 4.

For the ARM64 interpretation, original iOS 8.1 boot disassembly at `0xffffff80020d81e0` assembles `MAIR_EL1` from `0xff`, `0x4f00000000`, `0xbb0000`, and `0x4400`, yielding `0x0000004f00bb44ff`; AttrIndx 1 is exactly `0x44` and AttrIndx 3 is `0x00` in this boot path. The pmap entry builder is present in the original binary at `0xffffff80020c32e0`; its diagnostic literal names it `pmap_enter_options()`. It uses argument `w5 & 0xff` as the explicit WIMG value and dispatches it through a jump table at `0xffffff80020c45b4`. For WIMG value 6, the case at `0xffffff80020c3788` adds `0x4` to descriptor bits [4:2], selecting AttrIndx 1. The page descriptor is stored at `0xffffff80020c4564` (base-page path); the large-page path at `0xffffff80020c4520` uses the same attribute word. Thus the exact binary conversion WIMG 6 → AttrIndx 1 is established. Exact-era Apple XNU `xnu-2782.1.97` source declares `pmap_enter_options` argument 6 as `flags`, and its `IOProtectCacheMode` maps `kIOMapWriteCombineCache` to `VM_WIMG_WCOMB` before passing it as that argument. This confirms the meaning of the explicit WIMG path without relying on modern source.

That generic conversion does not by itself prove that the *initial G4G map fault* supplies WIMG 6. Exact-era `IOGeneralMemoryDescriptor::memoryReferenceCreate` source converts the physical default mode into device-pager flags 6 (`DEVICE_PAGER_CACHE_INHIB | DEVICE_PAGER_COHERENT`) and creates a device pager with them. The same source's `populateDevicePager` then populates the pager and forces a `vm_fault` for kernel mappings. In the kernelcache, the generic fault-to-pmap call at `0xffffff800207a118` explicitly sets `w5 = 0` before calling `pmap_enter_options`; it does not forward the device-pager flags as pmap's WIMG argument. With WIMG 0, the binary builder instead selects by physical range. The RGX page `0x201000000` is below the observed J81 DRAM base `0x800000000`; the out-of-range branch at `0xffffff80020c37dc` places `0xc` in descriptor bits [4:2], selecting AttrIndx 3 (MAIR byte `0x00`). This is the direct fault-path result if the kernel's prefault reaches that call with the RGX page, as the Apple source says it does. The write-combine WIMG 6 → AttrIndx 1 case is separately exercised by `IOMemoryDescriptor::redirect` at `0xffffff80023e420c`: that method derives 6 when its map's cache selector is mode 4 and passes it as pmap argument `w5`. It is a redirect/protect path, not proof that the initial page fault takes the same branch.

Sources: Apple [XNU `pmap.h` at xnu-2782.1.97](https://github.com/apple-oss-distributions/xnu/blob/xnu-2782.1.97/osfmk/vm/pmap.h), [XNU `iokit_rpc.c` at xnu-2782.1.97](https://github.com/apple-oss-distributions/xnu/blob/xnu-2782.1.97/osfmk/device/iokit_rpc.c), and [XNU `IOMemoryDescriptor.cpp` at xnu-2782.1.97](https://github.com/apple-oss-distributions/xnu/blob/xnu-2782.1.97/iokit/Kernel/IOMemoryDescriptor.cpp). Apple's public ARM64 XNU definitions independently name AttrIndx 1 `CACHE_ATTRINDX_WRITECOMB`; they are supporting terminology, not the proof of the old pmap conversion. See [XNU ARM64 `proc_reg.h`](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/proc_reg.h).

`doMap` calls the internal VM-enter routine at `0xffffff8002089f1c` to install the memory-entry mapping; it does not directly write a PTE. The pmap WIMG-to-PTE switch is now recovered, but the initial device-pager fault's `w5=0` means it takes the physical-range default path, not the explicit WIMG 6 path. Conditionally, the first-fault path points to AttrIndx 3 for this out-of-DRAM page, while IOKit's mode 4 remains a pager-level/write-combine request. `IOMemoryDescriptor::redirect` contains a separate mode-4/WIMG-6 path, but the offline artifacts do not establish that redirect is invoked for this RGX mapping. Do not equate device-pager flags 6 numerically with pmap WIMG flags 6. The original binary establishes these as different arguments and call paths.

### Follow-up: separate AGX auxiliary descriptor resolved; RGX remains open

The iOS 8.1 Mach-O symbol table resolves a *separate AGX auxiliary-resource*
constructor question. In
`FUN_ffffff800329d558`, the call target at `0xffffff80023de5a4` is the exported
symbol `IOMemoryDescriptor::withPhysicalAddress(IOPhysicalAddress,
IOByteCount, IODirection)`, not `IODeviceMemory::withRange`. For each of the
five records except index 4, the code passes the record's physical start, its
length rounded up to the kernel page size, and direction `3`
(`kIODirectionIn | kIODirectionOut`). The resulting generic IOMemoryDescriptor
describes a physical range; `3` is direction, not a cache-mode or tag.

The descriptor mapping call in `FUN_ffffff800329d6a4` passes options
`0x90007`. The cache field is `(options & 0xf00) >> 8 = 9`; Apple's IOKit
option encoding names mode 9 `kIOPostedCombinedReordered`
(`kIOMapPostedCombinedReordered = 0x900`). The low bits are `0x7`. Thus this
path explicitly requests IOKit's posted/combined/reordered mode, rather than
leaving cache selection at the descriptor default. The numeric encoding is
documented in Apple's `IOMapTypes.h`; the call values and symbol identity come
from the iOS 8.1 kernelcache. `tools/ghidra/README.md` identifies the imported
`AGX.raw` as the 12B410 `__PRELINK_TEXT` slice, and `nm -m` on the original
Mach-O kernelcache supplies the external C++ symbol names.

This result does not apply to the reg-index-0 RGX mapping: the loop explicitly
skips record 4, and the adjacent evidence identifies record 4 as
`0x201000000/0x20000`. It proves mode 9 only for the other auxiliary ranges.
The RGX provider path previously traced above maps with explicit options 0, so
its IOKit selector is the default. The pmap builder and the initial fault's
zero-WIMG argument are traced below; keep this auxiliary mode-9 result
separate from that provider path. Do not call mode 9 “uncached” or equate it
with a specific ARM memory type.

The separate reg-index-0 construction path is now resolved from original
kernelcache code. `IODTPlatformExpert::getNubResources` at
`0xffffff80023eae90` calls `IODTResolveAddressing` at
`0xffffff80023a69a8` when the nub has no preexisting device-memory array; it
passes the literal property name `reg` (`0xffffff800245c238`). For each
resolved `reg` tuple, `IODTResolveAddressing` calls
`IOMemoryDescriptor::withAddressRange(addr, len, 0x800, TASK_NULL)` and puts
the result in the service's device-memory array. The `withAddressRange`
implementation at `0xffffff80023de4d4` allocates an
`IOGeneralMemoryDescriptor`; null task selects physical type `0x20`, and the
caller option `0x800` is ORed in before `initWithOptions`. In this call path
`0x800` is `kIOMemoryMapperNone`; no cache-mode bits are supplied. This is the
physical descriptor from which the provider's `getDeviceMemoryWithIndex(0)`
map request operates.

For that reg-index-0 request, G4G passes map options `0`. The kernelcache's
`IOMemoryDescriptor::map(options)` implementation adds `kIOMapAnywhere` only,
then creates the kernel mapping; no cache-mode override is introduced. The
request selector is default (`kIODefaultCache`, mode 0), and the binary resolves
the physical-page default to mode 4 (`kIOWriteCombineCache`) because
`0x201000000` lies below the saved J81 DRAM interval. The candidate initial
fault PTE behavior and its runtime caveat are described below. Do not equate this with mode 9
(`kIOPostedCombinedReordered`) or device-nGnRnE.

For Linux `/dev/mem`, the pinned J81 test kernel's arm64
`phys_mem_access_prot()` selects `pgprot_noncached()` when
`pfn_is_map_memory(pfn)` is false; `O_SYNC` selects write-combine only for a
RAM PFN. Its `pgprot_noncached()` is AttrIndx `MT_DEVICE_nGnRnE`, while
`pgprot_device()`/`ioremap()` uses `MT_DEVICE_nGnRE`. The November 7
read-only control boot's `/proc/iomem` and runtime FDT show System RAM only at
`0x800c00000..0x87d0d5fff` and `0x87d0da000..0x87d0ddfff`; the GPU page at
`0x201000000` is outside both. This supports the non-RAM branch for that
control boot, not a direct PTE measurement or proof of memblock state during
the earlier test4 boot. See [the control snapshot](2026-11-07-j81-weekend-readonly-capture.md),
[pinned arm64 `mmu.c`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/mm/mmu.c),
[pinned `pgtable.h`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/include/asm/pgtable.h).

The mode-9 request above belongs to the auxiliary loop, whose record 4 is
exactly the RGX physical range and is skipped, so it cannot be attributed to
the reg-index-0 map. Test4 therefore compares the same physical address under
Linux's `/dev/mem` policy and Apple's provider-created mapping; it does not
compare Linux nGnRnE with Apple's auxiliary mode 9, nor prove the Apple PTE
type.

The separate AGX auxiliary-resource registration table skips its record 4
(`0x201000000/0x20000`); that does not mean Apple's G4G identity path lacks
an RGX map. The `reg`-indexed provider path above maps RGX before the identity
dispatch, while the auxiliary table is for a different resource-registration
path. Keep those map lifecycles distinct.

## Linux test4 path

`boot/gpu-core-revision-once.c` opens `/dev/mem` with `O_RDONLY | O_SYNC`,
maps `0x201000000` for one page with `PROT_READ | MAP_SHARED`, then reads one
volatile 32-bit word at `+0x20`. The physical base and read offset agree with
the J81 `reg` index 0 and Apple's first identity offset. Orchard's independent
J81 PIO setup also names core base `0x201000000` and length `0x20000`.

The pinned kernel's `/dev/mem` mmap path calls the arm64 protection hook.
That source-derived policy makes a normal cacheable-RAM mapping unlikely for
the observed non-RAM address, but the earlier test4 boot has no matching RAM
map snapshot. It does not prove the test4 PTE attributes, exclude conflicting
aliases, or show that Apple's map has the same memory type. The newer control
boot supports the address classification only for that boot.

## Remaining discriminator

The strongest mapping hypothesis is now narrower: Linux uses the same
physical resource base, but bypasses Apple's provider-created kernel mapping.
Apple's `+0x70` result is a CPU virtual address from the device-memory map,
not a device/DART address by the public API contract. The Apple map object's
internal `+0x80` can return its stored address field or delegate to a
descriptor-specific `+0xa8` address materializer, depending on state bit 6
(`2026-11-06-j81-provider-map-address.md`); that describes the private map
wrapper used in a separate selector path and is not proven to be the exact
object returned by provider `+0x3c8`. The builder's explicit WIMG-to-AttrIndx
conversion and the initial fault's default branch are traced above. No live
Apple PTE or alias-policy measurement exists.
The missing address materializer could still return a translated aperture in
that private wrapper path, but it must not be conflated with the public
`mapDeviceMemoryWithIndex` route established here.

Remaining limits: no live Apple PTE or alias-policy measurement exists, and
the exact runtime choice among the generic fault path and any later redirect
or cache-protection pass was not observed on device. Linux's live PTE
attributes were not measured.

Evidence: `artifacts/live/private/gpu-offline/gpc-link.c`, `gpc.c`,
`ident.c`, and `ios81-agx-disasm.txt` around `0xffffff80032935a0`,
`0xffffff80032933cc`, and `0xffffff800328de68`; local J81 ADT and
`boot/gpu-core-revision-once.c`; `t7001-start.c` for an independent provider
call-site; `nm -m`/`llvm-objdump` on local `kernelcache` for IOKit, DT resolver,
and descriptor-construction symbols; `ios81-memory-registration.c` for the
separate auxiliary descriptor and map options; `tools/ghidra/README.md` for
import provenance. No device access was performed.
