# J81 resource table and boot-descriptor dispatch

Offline static analysis of the iOS 8.1 AGX kernelcache recovered the
resource table consumed by `FUN_ffffff800329d558` (`ios81-memory-registration.c`).
The table begins at `DAT_ffffff80032b32f8`; each record is six 32-bit words,
with the physical base in the first two words and the allocation size in the
third word.  The registration loop visits records 0, 1, 2 and 3, but skips
record 4 explicitly (`lVar9 != 4`):

| record | physical base | size | registration |
|---:|---:|---:|---|
| 0 | `0x201e00000` | `0x2000` | physical descriptor, selector `0x90007`, then mapping |
| 1 | `0x201e10000` | `0x1000` | physical descriptor, selector `0x90007`, then mapping |
| 2 | `0x20e100000` | `0x2000` | physical descriptor, selector `0x90007`, then mapping |
| 3 | `0x20e104000` | `0x1000` | physical descriptor, selector `0x90007`, then mapping |
| 4 | `0x201000000` | `0x20000` | skipped by the resource-map loop |

The four registered records use `withPhysicalAddress(base aligned to the
kernel page size, size, alignment=3)`, then the private descriptor method
`+0x90(..., 0x90007)`, followed by `createMappingInTask(..., 0x101, ...)`.
Record 4 is the GPU core window already identified in the ADT and is not
treated as a firmware allocation by this path.  This makes the split between
GPU MMIO and firmware/resource buffers concrete without touching hardware.

The boot descriptor is assembled later by
`FUN_ffffff800329d7d8` (`ios81-thread-use.c`).  Its six fixed address-class
words are followed by a provider value from `gpu + 0xbe0`, a bootloader
address `0xe1c0000000`, and a second provider value from `gpu + 0x5c20`.
When the provider reports the optional five-entry table, each resource map's
`+0x80` result is translated through the AGX `+0x140` hook and stored at
descriptor offsets `0x130..0x154`, paired with a six-word metadata record at
`DAT_ffffff80032b32f8`.  No direct register write or firmware execution is
in this routine; it is construction of host-side boot metadata.

The AGX vtable data gives a useful boundary marker: the static table at
`0xffffff80032b3008` contains `FUN_ffffff800329d7d8` at the `+0xc0` slot and
`FUN_ffffff800329d49c` at `+0xa8`.  This identifies the slot numbers used by
the preparation/start sequence, but does **not** prove that the runtime object
keeps this exact vtable (the initializer calls `+0xc0` after changing object
state, so a subclass/overridden table is possible).  Treating the static slot
as the final firmware-start implementation would be circular; the concrete
runtime vtable remains a separate unresolved boundary.

Implication for Linux: the existing model can safely reserve `0x201000000`
as the core MMIO window and must not present it as one of the four
`0x90007` firmware/resource mappings.  The four auxiliary regions still need
an Apple-compatible device-visible mapping before firmware execution is
enabled.  The descriptor's downstream provider consumer and the meaning of
the six metadata classes remain unresolved, so the simulator stays
execution-disabled.

## Descriptor handoff and limit

The initializer gives the descriptor two corresponding addresses: the
address used to fill it at `param_1[0x18] = backing_base + uVar7`, and the
map-derived address at `param_1[0x23] = map_base + uVar7`. The builder calls
the accelerator's `+0x140` method on the latter with argument `1` and writes
the 32-bit result to `param_1[0xf] + 0x5c`, in the first control structure.
This is a concrete indirect handoff of a translated descriptor address; it
does not identify the downstream reader, prove the translation's address
domain, or prove the structure is visible to META. See
`ios81-init-allocation.c` and `ios81-thread-use.c` in the private offline
artifacts.

One further handoff is visible in `firmware-prepare.c`: the mapped address
of the root control structure, `param_1[0x1c]`, is passed through `+0x140`
with argument `1`, and the 32-bit result is stored in the preparation buffer
at the offset recorded at `param+0x55c`. The same routine places the translated
address of this preparation-buffer slot in the boot/config area. This traces
how a root pointer is packaged, but the available host decompilation does not
show a dereference of the root's `+0x5c` field or establish that META read it.

Slot 2 remains distinct from this descriptor. A public Rogue META header
defines the bootloader's META address as `0x40000000` and its device virtual
address as `0xe1c0000000` (the high and low words are `0xe1` and
`0xc0000000`), the exact pair seen in the J81 image and descriptor. A separate
public Rogue implementation calls `0xe1c0000000` the firmware heap base and
requires firmware code at the heap start for bootloader lookup. This is a
strong cross-driver mapping hypothesis, not proof that J81 configures the
same mapping, maps the same bytes, or uses the same startup ABI. The `+0x5c`
reader and J81 segment programming remain unresolved.

Sources: [Rogue 1.17 META header](https://chromium.googlesource.com/chromiumos/third_party/kernel/+/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h),
[Rogue heap layout](https://chromium.googlesource.com/chromiumos/third_party/kernel/+/refs/heads/firmware-fizz-10139.117.B-chromeos-4.4/drivers/gpu/drm/img-rogue/1.9/rgxheapconfig.h),
and [Android 3.18 Rogue initialization](https://android.googlesource.com/kernel/mediatek/+/android-mtk-3.18/drivers/staging/imgtec/rogue/rgxinit.c).

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff80032b32f8`, `ios81-memory-registration.c`, and
`ios81-thread-use.c`. No firmware or hardware access was performed.
