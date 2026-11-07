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

Thus neither candidate resolves the preparation receiver's runtime
`+0x140` target: the constructor-proven table is for another object, while the
static table matching `+0x208/+0x210` has an incompatible `+0x140` call
signature and no recovered vptr assignment. This leaves the device-visible
address mapping, DART ownership, and segment-2 consumer unresolved. The
follow-up used Java 21/Ghidra 12.1.4 against `AGX.raw` extracted from the
original iOS 8.1 kernelcache, plus `nm -nm` on that original kernelcache;
forced decompilation artifacts are in the private offline workspace. No
firmware execution or hardware access was performed.
