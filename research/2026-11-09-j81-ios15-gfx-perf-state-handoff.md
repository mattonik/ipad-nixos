# J81 iOS 15 GFX performance table and Fender state: static handoff

Offline analysis on 2026-11-09 of the local 19H422-associated iPadOS
15.8.8 kernelcache. No device access. The goal was to trace the consumer of
GFX performance data, not to infer a register programming sequence.

## The GFX frequency table reaches a second structure

The driver function containing `0xfffffff00666e504` reads
`perf-state-count` and `perf-states` from its provider. On the normal property
path, it checks that the count is at most 16 and that the data contains at
least eight bytes per entry, then copies the pairs into the receiver at
`+0x1a9c`; count is stored at `+0x1b9c`. It separately reads and validates
`perf-states-sram` into `+0x1b1c`. There is an alternate branch selected by a
global flag, so this describes the property path, not a runtime observation.

Another function at `0xfffffff006689cc0` takes the accelerator pointer at
its receiver's `+0x1a8`, reads the count at accelerator `+0x1b9c`, and stores
it at a second structure's `+0x2a0`. It reads the 16 frequency fields at
accelerator `+0x1a9c + i*8`, divides each by 1,000,000 and stores the
integer result at that structure's `+0x2a4 + i*4` (through `+0x2e0`). The
second structure's pointer is at the receiver's `+0x220`. The code also
fills adjacent power-management metadata, but this does not prove the memory
is firmware-visible or that firmware consumes it.

The multiply/shift in the instructions implements the division reported by
the decompiler. Only the first word of each frequency/voltage pair goes to
this particular MHz array; no claim is made here about all other consumers or
the SRAM table's destination. The array contains possible operating points,
not a measurement of the selected clock.

## A separate state bound is checked against Fender

The receiver constructor at `0xfffffff00669afa8` installs vptr
`0xfffffff006f2de28`. The extracted cache's table has
`0xfffffff00668735c` at vptr `+0x5a0`, `0xfffffff00668755c` at `+0x80`,
`0xfffffff006689cc0` at `+0xa0`, and `0xfffffff006692828` at `+0x240`.
These are static vtable observations; a different runtime subclass can
override them.

The `68735c` initializer calls the associated accelerator's `+0x850`
virtual factory, stores its returned object at receiver `+0x160`, obtains the
mapped GPC base from global mapping `0xfffffff007a4d8a8` via its `+0x78`
method, and passes that base into the object's vtable `+0` initializer. The
inspected accelerator constructor at `0xfffffff00669c824` installs vptr
`0xfffffff006f2f2d0`; that vtable's `+0x850` entry points to
`0xfffffff00669aff4`, the Fender-object factory. The factory installs the
Fender vtable at `0xfffffff006f2fee8`, whose initializer stores the GPC base
at object `+0x10`. Thus, if these constructor-installed vtables remain in
use, this is a concrete static binding from the receiver to the Fender
object and the mapped GPC base. It is not a runtime trace.

The `68755c` function starts with a default of 3, reads provider property
`gpu-num-perf-states` if present, and considers the separate
`gpu_limit_max_pstates` input; it records the bounded result at receiver
`+0x57c`. The independently captured J81 ADT has `gpu-num-perf-states = 4`,
but its exact runtime value and the additional input on an iOS boot are not
established. Function `689cc0` writes receiver `+0x57c` to the second
structure at `+0x29c`. This bound is distinct from `+0x2a0`, which receives
`perf-state-count`.

The `692828` predicate, when receiver `+0x160` is non-null, calls the
Fender object's `+0x18` getter and rejects values below 1 or above that
`+0x29c` bound. It also calls Fender vtable `+0x78`; under the recovered
vtable that routine reads GPC control `+0` and tests bit 29, with a set bit
causing the predicate to reject. The getter's enable byte `+0xc`, active
runtime vtable and value of the limit are not established by Linux captures.

The host-paced Linux test separately observed GPC state `1` and control
`0x40000000` (bit 29 clear). **If** the iOS static binding, getter-enable byte
and a limit of at least 1 held, those values would satisfy the listed state
and control portions of this predicate. They do not prove the predicate ran,
that the selected GPU frequency equals table entry 1, or that RGX registers
are reachable. The predicate and this data-structure handoff are separate
from the already traced direct pre-ID probe; no pre-ID invocation of this
predicate is established.

## Evidence and limits

The cache SHA-256 is
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
Private artifacts include `ios15-perf-consumers.c`,
`ios15-agx-disasm.txt`, `ios15-fw-objects.c`,
`ios15-gpu-access-predicate.c`, and `rea-ios15-perf-handoff-20261109.json`
under `artifacts/live/private/gpu-offline/`. Static pointer arithmetic was
cross-checked against the raw cache's `__PLK_DATA_CONST` vtable entries.
The paired Linux capture and iOS ADT come from different contexts; they are
not a live iOS measurement. Neither the actual GFX frequency selector nor
its current value is identified.

The next offline target is the second structure's allocation and any
firmware or driver reader of the MHz array, plus the call chain that changes
Fender state and the predicate's runtime eligibility. This finding does not
justify adding a guessed GFX or GPC write to a hardware test.

Follow-up: [allocation, CPU reader and state-call analysis](2026-11-09-j81-ios15-perf-buffer-consumer.md).
