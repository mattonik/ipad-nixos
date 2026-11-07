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

The next useful evidence is a static trace of the mapper/descriptor methods
behind `32a6018`, `329a690`, and `329a6b4`, plus any firmware-init object that
publishes the mapped allocation's device address. A complete matching J81 META
image with its load map would then allow tracing writes to `base+0x60`, event
type 0, and its interrupt/doorbell sequence. Until that bridge exists, keep
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
