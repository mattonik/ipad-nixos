# J81 staging map: runtime-consumer boundary

The preparation allocation's `IOMemoryMap` is still only proven host-visible.
The preparation path stores its map object at AGX `+0x570`, calls vtable
`+0x80` (`IOMemoryMap::getVirtualAddress()`), and copies LDR bytes into that
CPU address. I scanned direct `0x570` field immediates across the complete
AGX raw image in Ghidra. The matching object path references are the prepare
routine (`0xffffff800329e63c`), its CPU copy/parser (`0xffffff800329fbe8`),
the destructor (`0xffffff800329d72c`), and the static-table `+0x210`
candidate (`0xffffff80032a0f30`).

The candidate `+0x210` body loops over resource maps at `+0x578..+0x598`,
passing each record pointer, the map object's `+0x18` descriptor pointer,
and a label such as `"Firmware PIO %s"` through an indirect helper. It does
the same for the preparation map with label `"Firmware Image"`. The body
ignores preparation-call argument `x2` (the slot index). Decompiling helper
`0xffffff800326bd38` shows that it checks descriptor flags, then calls
`0xffffff800326b8a4` with the record pointer and descriptor. That routine is
a hash-bucket lookup rooted at the first argument and keyed by the second;
the helper then gets or creates a `"Descriptions"` `OSArray` on the returned
object and appends the supplied label as an `OSString`. Its allocator/string
wrappers resolve to kernel `OSArray::withCapacity`,
`OSMetaClassBase::safeMetaCast`, and `OSString::withCString` via the original
kernelcache GOT.

This is a concrete host-side metadata consumer: it dereferences the passed
record pointer as the root of a custom object table, keyed by the descriptor,
and adds a description label. It does not translate the pointer, create a
DART entry, populate a segment descriptor, or write MMIO. Because the
`+0x210` method is still only a static-vtable candidate and its first argument
is a pointer into the mapped preparation allocation, the custom table's
runtime ownership/validity remains unproven; do not reinterpret this as a
device mapping or call it mere logging.

The original AGX raw image's GOT resolves the string-formatting stub
`0xffffff80032a645c` to kernel `_snprintf` at `0xffffff80023203a4`. It
formats the `"Firmware PIO %s"` stack label. Stub `0xffffff80032a61a4`
loads `0xffffff800326bd38` from AGX GOT slot `0xffffff80032ac300`. The
kernelcache `__PRELINK_TEXT` range was extracted at the README base and
imported into a scratch Ghidra project with whole-image analysis disabled;
`MakeFuncDecomp` forced the target and its helper functions, and a range
disassembly confirmed argument flow.

The public Rogue code is a useful contrast, not an Apple implementation
proof: its firmware allocator explicitly calls `DevmemAcquireDevVirtAddr`
and asserts that FW code has the expected firmware-heap device virtual
address. Apple's traced preparation path exposes a CPU virtual address and
passes it to an unresolved indirect helper; no equivalent device-address
acquisition has been identified. The exact bridge therefore remains the
helper target(s), not the arithmetic from raw META address to CPU staging
offset.

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff800329e63c..0xffffff800329e774` and
`0xffffff80032a0f4c..0xffffff80032a0fec`; Ghidra `FindImm.java` over
`AGX.raw` at base `0xffffff8003281000` (Java 21, see
`tools/ghidra/README.md`); the scratch-only extraction of kernelcache
`__PRELINK_TEXT` used file offset `5414912`, size `14114816`, base
`0xffffff8002593000`; and `nm -nm` on that kernelcache. Forced target
decompilation/disassembly: `0xffffff800326bd38`,
`0xffffff800326b8a4`, `0xffffff800326eca0`, `0xffffff800326ec1c`, and
`0xffffff800326ece8`. Public comparator:
[Imagination Rogue `rgx_meta.h`](https://chromium.googlesource.com/chromiumos/third_party/kernel/+/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h)
defines the META bootloader address/device-virtual address, while
[Rogue `rgxinit.c`](https://android.googlesource.com/kernel/mediatek/+/android-mtk-3.18/drivers/staging/imgtec/rogue/rgxinit.c)
shows explicit device-virtual acquisition for firmware code. No firmware was
executed and no hardware was accessed.

## Vptr and `+0x140` exclusion

A follow-up checked whether the address translator in the separate static table
at `0xffffff80032b3008` could be the preparation receiver's `+0x140` method.
Its entries are superficially attractive: `+0x208 -> FUN_...329f1a4`,
`+0x210 -> FUN_...32a0f30`, and `+0x140 -> FUN_...329c950`. However, the
`FUN_...329c950` body treats its third argument as an output pointer and
writes through it; the preparation routine at `0xffffff800329e63c` calls
`+0x140` with literal `1` or `0` as the third argument. That table entry is
therefore ABI-incompatible with the observed call.

The table that is directly installed by constructors
`0xffffff8003298cfc`, `0xffffff8003298de0`, and `0xffffff80032994b0` is at
`0xffffff80032b2d80`. Its `+0x140` entry resolves to
`0xffffff800238dc04`, which the original kernelcache symbol table names
`___cxa_pure_virtual`. The constructor/deallocator chain shows this is a
separate subobject, not proof of the preparation receiver's dynamic class.
There is no recovered store or code reference assigning
`0xffffff80032b3008` to the receiver in `FUN_...329e63c`.

This exclusion is superseded by the address-point correction below: the full
`AGXMetaFirmware` constructor installs a different address point than either
group-start table interpretation considered here. The group-start candidates
remain useful only as context for the initial subobject/base initializer.

## Address-point correction: dynamic `AGXMetaFirmware` receiver resolved

The preceding exclusion used the table start as the object's vptr. That was
the wrong address point for this class: its constructors install a pointer
0x38 bytes into the table group at `0xffffff80032b3008`. In particular, the
group-relative `+0x208 -> FUN_...329f1a4` entry is not the installed object's
runtime `+0x208` method; the installed method is `FUN_...329d0c4`.

In the original `AGX.raw`, `FUN_ffffff800329d384` registers the metaclass name
`AGXMetaFirmware` and instance size `0x5f8`. The allocation constructor
`FUN_ffffff800329d3bc` calls the shared initializer
`FUN_ffffff8003298cfc` and then overwrites `*this` with
`PTR_thunk_FUN_ffffff8003298de0_ffffff80032b3040`. The in-place constructors
`FUN_ffffff800329d40c` and `FUN_ffffff800329d454` do the same. Thus
`0xffffff80032b3040` (group base + `0x38`) is the installed vptr/address point
for the full `AGXMetaFirmware` object; the earlier `0x32b2d80` pointer is only
the transient shared/base initializer value.

Using that installed address point gives the actual slots used by the prepare
routine at `0xffffff800329e63c`:

| Receiver slot | Resolved entry | Evidence |
| --- | --- | --- |
| `+0x140` | `FUN_ffffff800329ff28` | Address point `0x32b3040 + 0x140` |
| `+0x210` | code at `0xffffff800329fea0` | Address point `0x32b3040 + 0x210` |

The `+0x80` map accessor in the preparation routine is called on the returned
`IOMemoryMap`, not on this `AGXMetaFirmware` receiver; do not infer it from this
table. The `+0x140` implementation is the translation the earlier note
missed. Its
64-bit result is `(arg1 - 0xe1c0000000) | region`, with `region` selected
between `0x40000000` and `0xc0000000` using the third argument and the object's
`+0x5cc` flag. At each identified init-data callsite the result is assigned to
a 32-bit field, so the observable address is the low 32 bits after this
unsigned 64-bit subtraction and OR. The preparation caller passes the two
previously initialized addresses (`param_1[0x1c]`, `param_1[0x2c]`) with flags
1 and 0, then the staging map address plus its parsed offset with flag 1.

Upstream provenance: the descriptor is created by
`thunk_EXT_FUN_ffffff800326dfa4`; its vtable `+0x90` is called with the task
value at device-object `+0x128` and mapping options, and the returned handle
is subsequently used as an `IOMemoryMap` (including its vtable `+0x80`
address accessor). The original iOS 8.1 kernelcache exports
`IOMemoryMap::getVirtualAddress` at `0xffffff80023e4640`. Apple XNU's
[IOMemoryDescriptor mapping API](https://developer.apple.com/documentation/kernel/iomemorydescriptor/1441859-createmappingintask)
documents that a mapping is into a specified task and its `IOMemoryMap`
supplies that task's virtual address. Thus these inputs are task VAs, not
already translated GPU/DART VAs. The exact virtual target behind the
descriptor's `+0x90` dispatch is not named by this analysis, and the device
object's `+0x128` task value is passed through; this static trace does not
prove that it is `kernel_task`. The translation into 32-bit META-init fields
is directly proven, while the subsequent hardware/DART ownership or mapping
that makes those addresses usable remains unproven.

The actual `+0x210` entry begins at `0x329fea0` (inside the end of the preceding
function as Ghidra's default function boundaries show). It consumes the third
argument as the descriptor index and appends META register records; it is not
the static-table candidate `0x32a0f30`. That candidate was indexed from the
group start and therefore was not a valid substitute for the installed object
vptr. The helper `0x32a0f30` remains a separate static-table candidate and its
metadata behavior does not alter this runtime slot resolution.

Reproduction: Java 21/Ghidra 12.1.4, scratch project `agx`, original iOS 8.1
`AGX.raw` at base `0xffffff8003281000`, and helpers documented in
`tools/ghidra/README.md`. Decompiled constructors are in private offline
`j81-near.c`; forced decompilation of `0x329ff28` is in `j81-resolved.c`;
`ios81-agx-disasm.txt` at `0x329fea0..0x329ff50` confirms the slot body and
region selection. As a generation-distant architecture comparator, the public
[Asahi AGX notes](https://asahilinux.org/docs/hw/soc/agx/) describe modern
AGX UAT and firmware-init address spaces; they support keeping GPU/firmware
address spaces distinct but do not prove the iOS 8.1 implementation here.
No firmware was executed and no hardware was accessed.
