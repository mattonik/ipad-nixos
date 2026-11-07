# J81 alive producer boundary (offline, 2026-11-07)

This follow-up checks whether the remaining event-ring producer can be named
from the preserved META image or the existing firmware Ghidra material. It
uses static artifacts only; no firmware was run and no device was accessed.

## Source candidates narrowed to AIC 134 or 138

The dispatch note establishes the captured `/arm-io/sgx` one-cell AIC
interrupt list as `[134, 135, 136, 137, 138]`. AGX builds five
`IOFilterInterruptEventSource`s by ordinal; the action routes normalized
ordinals 0 and 4 to the common event-ring drain and routes 1–3 elsewhere.
Therefore, under the captured property order and five-source initialization,
only AIC sources 134 and 138 can make the host drain the ring and deliver
record type 0 to the alive callback. This is an exhaustive candidate set for
that path, not a finding that either source is the alive interrupt: both
invoke the same drain, and the drain dispatches every queued record it sees.
An interrupt can consequently drain an event produced earlier by another
source. The host code does not associate ring records with an interrupt
ordinal.

## Host allocation and mapped ring offsets recovered

The setup routine at `0xffffff80032998d8` creates a memory descriptor through
the AGX import stub at `0xffffff80032a6018`, maps `0x780000` bytes into the
provider task (the call at `0xffffff800329a660`, followed by the mapping call
at `0xffffff800329a690`), then obtains the mapped virtual base at
`0xffffff800329a6a0`–`0xffffff800329a6b8`. It stores the descriptor at AGX
`+0x268`, the returned map at `+0x270`, and the returned mapped base at
`+0x158`. From that base it sets the event-ring state pointer at AGX `+0x1e8`
to `base + 0x50`, and the event-record pointer at AGX `+0x208` to
`base + 0x130` (`0xffffff800329a6c0`–`0xffffff800329a6e4`).

Combined with the existing drain disassembly, the shared mapped layout is:

| Address relative to mapped base | Host use | Evidence |
|---:|---|---|
| `+0x50` | ring state; consumer index at `+0`, producer snapshot at `+0x10` | `329b7f8` reads state through `this+0x1e8`; consumer advances at state `+0` and snapshots state `+0x10` |
| `+0x60` | producer-index word address | inferred from the producer index field at state `+0x10` |
| `+0x130` | record slot 0 | `329b7f8` reads records through `this+0x208` |
| `+0x130 .. +0x292f` | 256 × `0x28`-byte records (`0x2800` bytes) | record stride and 8-bit wrap from `329b7f8` |

This is a concrete host allocation and CPU-mapped-address relationship. The
map object and descriptor establish that the buffer is backed by an
`IOMemoryDescriptor`/mapping path; the recovered code does not establish the
GPU/META-visible address corresponding to the CPU base, nor show this base or
`base+0x60` written into a firmware boot descriptor. The producer-index
location is therefore identified in the host mapping but not in a proven
device address domain. The host-side ring allocation is now recovered; the
firmware writer and its notification/doorbell path remain unavailable.

There is a partial descriptor handoff clue, but it does not close the address
translation: initialization at `0xffffff800329e7c8` passes another mapped-base
pointer (`this+0x160`) through virtual slot `+0x140` and stores the 32-bit
return in a structure. The slot target in the `AGXAcceleratorG4G_A0`
vtable resolves to `IOService::serializeProperties`, so this call does not
identify a GPU-address translator. No evidence equates that serialized word
with the event ring's `base+0x130` or the producer index at `base+0x60`.

The local `g4g81-image.bin` is a META LDR payload: the existing metadata report
identifies its small boot/load records and staging logic, but it is not a
recoverable full firmware address-space dump. `artifacts/live/private/ghidra-j81`
contains `fw12` ARM/Thumb Ghidra imports and decompilations for a separate
touch firmware image (`touch-fw-arm*.bin` in project metadata). Those ARM
programs cannot establish the J81 GPU META ring writer. The local Ghidra recipe
in `tools/ghidra/README.md` is for raw iOS 8.1 kernelcache imports; it does not
provide the missing GPU firmware image or firmware runtime memory map. Thus a
producer trace cannot be justified by importing/renaming the available ARM
programs or scanning the LDR payload as if it were complete firmware.

Public newer-generation material is not a safe substitute: the G17P ABI
describes a 72-byte (`0x48`) event entry and a newer ASC/mailbox path, whereas
the captured J81 host drain reads 40-byte (`0x28`) entries and dispatches
through the A8X META/AIC setup. That public source is useful as a generation
contrast only; neither its ring layout nor its notification path identifies
J81's producer.

## Evidence needed to close the device-address boundary

The `32a6018` import stub and `329a660` allocator are now traced to the
IOAccelerator wrapper allocator. The next useful evidence is the concrete
runtime vtable targets for wrapper `+0x90` and backing object `+0x140`, plus
any firmware-init object that publishes the returned value. A complete matching
J81 META image with its load map would then allow tracing writes to
`base+0x60`, event type 0, and its interrupt/doorbell sequence. Until that bridge exists, keep
134/138 as shared-drain candidates and do not invent a Linux producer protocol
or equate the CPU pointer with a device address.

Evidence references: `2026-11-07-j81-g4g-event-dispatch.md` (source ordinal
dispatch and ring drain); `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt`
(allocator/map and offset stores at `329a660`–`329a6e4`); read-only Ghidra
`FindImm.java` and `DecompTo.java` queries against `AGX.raw` (field and
function cross-check); `ios81-postldr.c` (host consumer); `tools/ghidra/README.md`
and the `fw12*.rep/idata` project metadata (scope of available firmware
imports); `tools/gpu_ldr_inspect.py` and
`2026-11-07-j81-meta-slot2-raw-address-and-staging.md` (LDR image limits);
[newer G17P event ABI](https://github.com/mischa85/apple-gpu-firmware-abi/blob/main/04-events-recovery-memory.md)
(generation comparison only).

## The ring allocation is an IOAccelerator wrapper, not a direct kernel descriptor factory

Following the indirect branch for `0xffffff800329a660` resolves its callee to
`0xffffff800326dfa4` in the separately imported `IOAcceleratorFamily2.raw`
program. The caller stub at `0xffffff80032a6018` loads this external address
from the AGX import cell at `0xffffff80032ac1d0`. A Ghidra decompilation of
`326dfa4` shows a wrapper allocator:

1. call provider vtable `+0x608` to obtain a size limit and reject a request
   larger than that limit;
2. call provider vtable `+0x5e8` to create the backing object, passing the
   class-like argument, option/flag argument, size, and provider data;
3. allocate a wrapper through provider vtable `+0x598`;
4. store the backing object at wrapper `+0x80`, options at `+0x38`, size at
   `+0x40`, selector/flags at `+0x88`, and related state at `+0x30`, `+0x70`,
   and `+0x90`.

The arguments at `329a660` are `(provider, DAT_32ac558, 0, 0, flags, 0x780000)`.
The returned wrapper is stored at AGX `+0x268`. Therefore the `+0x268` field
is the retained IOAccelerator wrapper; it is not proven to be a raw
`IOMemoryDescriptor`. At `329a690`, the caller invokes that wrapper's virtual
slot `+0x90` with `(task, 0x780000)` and saves the returned object at AGX
`+0x270`. The next call at `329a6a0` follows the wrapper's `+0x80` backing
object and dispatches virtual slot `+0x140`; its result is the base saved at
AGX `+0x158`. Thus the precise chain is wrapper → backing object and map
handle → backing object's private `+0x140` address method.

The iOS 8.1 kernelcache exports `IOMemoryDescriptor::createMappingInTask`
at `0xffffff80023e4840` and `IOMemoryMap::getVirtualAddress` at
`0xffffff80023e4640`; the latter simply loads object field `+0x28`, and its
vtable slot is `+0x80`. Those public kernel methods do not identify the
private `+0x90` or `+0x140` targets in this chain. In particular, the AGX
`+0x140` result cannot be called a CPU `IOMemoryMap` virtual address based on
slot number or nearby code alone. The call may apply the private wrapper's
mapping policy, but its target vtable and address domain remain untraced.

This is a meaningful narrowing: `329a660` is now identified as the
IOAccelerator-family allocation/wrapper helper, and the intervening object
roles are explicit, while the decisive private `+0x140` method still has no
resolved callee or address-domain proof. No `createMappingInTask` direct call
occurs in the shown `329a660`–`329a6b8` sequence. The CPU base is being used to
form host pointers (`+0x50`, `+0x130`, and other offsets), but proving a GPU
address still requires resolving the backing object's runtime vtable target
for `+0x140` and finding where that returned value is published to firmware.

Evidence: `ios81-agx-disasm.txt` at `329a660`–`329a6b8`, `32a6018`, and
`32ac1d0`; Ghidra `DecompTo.java` against `IOAcceleratorFamily2.raw` at
`0xffffff800326dfa4` (preserved in `artifacts/live/private/gpu-offline/ios81-ring-allocator.c`); the
kernelcache's `nm` exports for the public mapping methods; and the prior
`2026-11-06-j81-iomemorymap-address-getter.md`. All analysis is static; no
device or firmware was used.

## `AGXMetaFirmware +0x140` is not yet the ring backing-object method

The newly recovered `AGXMetaFirmware` vptr at `0xffffff80032b3040` and its
`+0x140` translator (`FUN_ffffff800329ff28`) explain a separate call chain:
preparation passes CPU addresses obtained from `IOMemoryMap::getVirtualAddress`
through that receiver to produce META-style addresses. The event-ring call
at `329a6a0` has a different receiver: it reloads the wrapper at AGX `+0x268`,
loads the backing object stored at wrapper `+0x80`, and calls that object's
`+0x140`. The allocator at `326dfa4` obtains the backing object dynamically
from provider vtable `+0x5e8`; it does not set or check that object's vptr.
No static evidence currently equates it with `AGXMetaFirmware` or proves that
the event-ring base is passed through `FUN_329ff28`. Therefore the known
CPU-to-META conversion cannot yet be applied to the ring or its producer-index
address. The remaining obstruction is the runtime class/vptr returned by
provider `+0x5e8` and the concrete targets for the wrapper `+0x90` and backing
object `+0x140` slots.

Cross-reference: `research/2026-11-07-j81-staging-map-runtime-consumer.md`
(the firmware-object vptr and translator); `ios81-ring-allocator.c`
(IOAccelerator wrapper helper). Static evidence only.
