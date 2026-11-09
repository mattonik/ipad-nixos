# J81 GPC state versus the GFX performance table

Offline analysis on 2026-11-09 of the local 19H422-associated iPadOS 15.8.8
kernelcache and 12B410 iOS 8.1 AGX artifacts. No iPad access. This follows
the [page-5 investigation](2026-11-09-j81-llb-page5-clock-dataflow.md)
and the campaign captures.

## The iOS 15 Fender object has a state setter and getter

The 15.8.8 kernelcache contains the diagnostic signature
`G4G_A0::AGXFenderCommon::setGPCPerformanceState`. In the extracted code,
`0xfffffff00669aff4` allocates an object and installs the vtable address
`0xfffffff006f2fee8`. In the full local kernelcache, the pointer at vtable
`+0x10` resolves to `0xfffffff006698d94`, and the pointer at `+0x18`
resolves to `0xfffffff006698f24`. The initializer at `0xfffffff00669bbac`
stores its second argument as the object's base pointer at `+0x10` and
sets the byte at `+0xc` and word at `+8` to zero.

Instruction review shows:

- The setter at `698d94` reads `base+0x1000`, waits for bit 4 to clear,
  writes `requested_state | 0x10`, reads that register back, and stores the
  request at object `+8`. Its timeout path and its conditional wait differ
  from the direct pre-ID probe sequence; it is not established that this
  particular object or virtual method runs before the ID read.
- The adjacent vtable entry at `698f24` is an interior entry point which
  Ghidra incorrectly merges into the prior function. Starting at the actual
  vtable target, the instructions test object byte `+0xc`: if zero, they
  return zero; otherwise they read `base+0x1000` and return its low nibble.
  This is a separate callable entry in the recovered static vtable, not a
  claim that the decompiler's merged control flow is correct.
- On J81, the independently traced G4G pre-ID path maps GPC at
  `0x201e00000` and uses its `+0x1000` register. The campaign observed that
  physical register return `0x1` after initialization. If this Fender object
  is bound to the same mapping and its getter's enable byte is set, the
  getter would return `1`. The actual iOS runtime object, its enable byte and
  an iOS execution of that getter were not observed here.

The code and diagnostic name make `+0x1000` a concrete GPC performance-state
interface in this driver. They do **not** show that its numeric values select
the entries at `0x20e01c000 + n*0x10`, that GPC state 1 means GFX perf-table
entry 1, or what frequency the GPU clock has. The state-1 observation does
not prove the core is clocked.

## The device-tree GFX table is handed to a separate structure

The 8.1 AGX `configureDevice` path at `0xffffff8003284cc8` reads the
`perf-state-count` and `perf-states` properties and copies the frequency/
voltage pairs into the accelerator object at `+0x5d2c`, with count at
`+0x5dac`. Later, descriptor builder `0xffffff800329d7d8` writes the count
at descriptor `+0x174` and copies 16 pairs into the descriptor beginning at
`+0x178`. The same builder writes other boot metadata and a translated
address into a control structure, as documented in the
[descriptor dispatch trace](2026-11-07-j81-resource-table-and-descriptor-dispatch.md).

This is evidence of a host-side metadata handoff. It does not establish
which agent eventually reads the table, that META firmware has started, or
that the 8.1 descriptor layout applies to 15.8.8. It also does not identify a
PMGR GFX selector or prove that the descriptor is involved before the first
GPU ID read. The 15.8.8 G4G pre-ID sequence independently shows a direct GPC
request of `0x11` before that read; the separate setter/getter above should
not be substituted into that sequence without a proven call edge.

## Next evidence target

Trace the provider/controller that consumes the GFX frequency table or the
selector controls around the dedicated `0x20e01c000` block. The current
kernel scan and paired Linux snapshots do not establish the selected GFX
frequency, and the vtable result gives no new safe register-write recipe.
A working iPadOS trace could resolve runtime ordering, but its required boot
instrumentation and retrieval path are not yet implemented or validated.

Evidence: the local decoded 19H422-associated kernelcache SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`,
`ios15-agx-code.raw` SHA-256
`9543debbf2d4bdb80c44cd2c6e9d2bb651631ce9d3561cd8b63c7bd9f0269d50`,
private `rea-gpc-perf-20261109.json`, `ios15-agx-disasm.txt`, `gpc.c` and
`ios81-thread-use.c` under `artifacts/live/private/gpu-offline/`, and the
local campaign logs. Static vtables and decompiled bodies do not prove
runtime binding; the private binaries are not included in this repository.
