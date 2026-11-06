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

Implication for Linux: the existing model can safely reserve `0x201000000`
as the core MMIO window and must not present it as one of the four
`0x90007` firmware/resource mappings.  The four auxiliary regions still need
an Apple-compatible device-visible mapping before firmware execution is
enabled.  The descriptor's downstream provider consumer and the meaning of
the six metadata classes remain unresolved, so the simulator stays
execution-disabled.

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff80032b32f8`, `ios81-memory-registration.c`, and
`ios81-thread-use.c`. No firmware or hardware access was performed.
