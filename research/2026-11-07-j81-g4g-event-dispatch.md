# J81 G4G alive-event dispatch boundary (offline, 2026-11-07)

This note follows the unresolved producer/dispatch item in
[`2026-11-06-j81-g4g-alive-contract.md`](2026-11-06-j81-g4g-alive-contract.md).
It uses only the local iOS 8.1 kernelcache and the preserved Ghidra
decompilation/disassembly under `artifacts/live/private/gpu-offline/`.
No firmware was executed and no device was accessed.

## Resolved: `provider+0xaf8` is the wait/wakeup gate

The recovered wait routine `0xffffff800329e894` gets an object from
`provider + 0xaf8` and calls its vtable at object offsets `+0x108`; the alive
callback `0xffffff800329f6cc` calls the same object's `+0x100` method with
`&this[0x5ca]`.

The iOS 8.1 kernelcache exports `__ZTV13IOCommandGate` at
`0xffffff8002492ca0`. Its vtable layout includes:

| Object vtable offset | Kernelcache target | Symbol |
|---|---:|---|
| `+0x100` | `0xffffff80023d2c8c` | `IOCommandGate::commandWakeup(void *, bool)` |
| `+0x108` | `0xffffff80023d2c18` | `IOCommandGate::commandSleep(void *, uint64_t, uint32_t)` |

These offsets are relative to the vptr stored in the object; the vtable
symbol's two-word prefix accounts for the `+0x10` difference. The symbol
addresses and method slots were checked against `nm` output and the raw
`__DATA,__const` entries in the local kernelcache. This resolves the object
identity to an `IOCommandGate` and the calls to a condition wait / wakeup pair.
The iOS wait loop first converts a one-second interval to a deadline, then
uses the gate's timed sleep; event type 0 sets the latch and wakes waiters.

This changes the interpretation of the earlier shorthand “event source”:
`provider+0xaf8` is the host synchronization gate used by the callback and
waiter. It is not itself evidence of an `IOInterruptEventSource`, a firmware
mailbox, or a particular interrupt line.

## Callback and runtime dispatch evidence

The callback body at `0xffffff800329f6cc` is present in the recovered main AGX
text, and its address is stored in the firmware-object vtable at
`0xffffff80032b3230`. In the table based at `0xffffff80032b30a8`, that is
slot `+0x188`. This table is separate from the `AGXAcceleratorG4G_A0` vtable
at `0xffffff80032aefa0` (the latter's `+0x188` is inherited
`IOService::mapDeviceMemoryWithIndex`). The available trace identifies the
callback's owner as the internal firmware object, but does not establish its
exact runtime class name. Its known behavior is narrow:

* event type 0, if the `+0x5ca` alive latch is clear, copies `event[2]` to
  `this+0x5d0`, sets `this+0x5c9` and `this+0x5ca`, then wakes the gate;
* event type 6 takes a separate META reset/recovery path;
* other event types return without changing the alive latch.

The read-only Ghidra `FindXrefs.java` query against the loaded `AGX.raw`
program (`-process AGX.raw -noanalysis`, targets `329f6cc` and `32b3230`)
found only `32b3230 -> 329f6cc`; no code call site points directly to the
callback. This is consistent with indirect framework dispatch or registration
outside the main-AGX text; it does not identify the invoking object or
registration routine. The firmware-object vtable and boot-wait callers
establish the callback's runtime role, but not its event producer.

The main AGX publisher at `0xffffff8002665130` creates a concrete firmware
service through accelerator vtable `+0x570`, attaches it, and calls
`registerService(0)`. The separate `AGXFirmwareKextG4G` class has its own
vptr `0xffffff8002e50080`; its `start` override only delegates to
`IOService::start` and re-registers the service. These lifecycle findings do
not connect that service object's vtable to `329f6cc`, whose pointer is in the
distinct `32b30a8` firmware-object table.

Separately, routine `0xffffff80032871f0` reads provider properties named
`interrupts` and `meta-sw-interrupt` and stores their metadata in the AGX
object. This is evidence that the accelerator consumes interrupt
configuration; the routine contains no visible interrupt-source creation or
callback registration. A later import-slot trace found a direct call to the
`IOInterruptEventSource` factory elsewhere in AGX, but its action and null
provider do not establish registration of this candidate path. No direct
`IOService::registerInterrupt` call was found; indirect paths remain unresolved.

The local kernelcache contains `IOInterruptEventSource` symbols, but the
recovered evidence examined here does not connect those symbols to this
callback. No interrupt handler, interrupt vector, GPU/META status-bit source,
or event-0 producer has been identified. Therefore the end-to-end chain

```text
META/GPU event -> interrupt source/handler -> callback event 0 -> gate wakeup -> host alive latch
```

remains incomplete at its first two arrows. The callback/gate segment is
statically supported; the producer and interrupt dispatch remain unknown.

## Linux relevance

The local Orchard A10 integration is a separate A10/T8010 design: it boots a
flat image via RTKit, uses shared-memory init data, and documents that RGX
interrupts route to the firmware coprocessor. It is useful as a counterexample
to assuming the upstream PowerVR interrupt path applies unchanged, but it does
not establish an A8X/J81 transport or interrupt contract. The generic META
FWIF boot flag likewise remains a different completion contract. No Linux
adapter can be justified from the gate/callback evidence alone.

Next offline target: identify the code that registers or dispatches the
internal firmware-object virtual callback and independently trace the A8X
provider's GPU interrupt source. Until those are joined by evidence, keep
event 0 a host-model input rather than an assumed Linux interrupt completion.

## J81 interrupt metadata narrowed (still no dispatch join)

The preserved iOS 8.1 ADT JSON at
`artifacts/live/private/gpu-offline/ios81-dt.json` has one `/arm-io/sgx`
node (`compatible = "gpu,t7001"`) with `interrupt-parent = [301989888]` and
`interrupts = [134, 135, 136, 137, 138]`. This is five advertised interrupt
entries, not a mapping from an entry to event type 0. The parent phandle still
needs resolution to interpret those cells; the AGX initializer at
`0xffffff80032871f0` also reads the independent `meta-sw-interrupt` property.

This narrows the next static target: resolve the `interrupt-parent` phandle and
cell encoding from the same captured ADT, then trace the generic IOKit property
consumer / interrupt-source registration path for each of the five entries.
Only a registration whose handler or callback reaches the internal firmware
object callback at `0xffffff800329f6cc` would join the chain. The examined AGX
text has no direct registration call or direct call to that callback, and no
such joining reference was found in the checked xrefs. Keep the five ADT lines
as candidates, not as identified META vectors.

Public Asahi documentation describes the much newer G17P host/firmware model
as mailbox notifications joined to a firmware event ring, and documents a
separate GFX ASC interrupt task. That material is explicitly about newer Apple
Silicon and does not establish the T7001/G4G mechanism; it is useful only to
avoid conflating a modern ASC path with this META-era host callback. See
[Asahi AGX notes](https://asahilinux.org/docs/hw/soc/agx/) and the
[G17P ABI overview](https://github.com/mischa85/apple-gpu-firmware-abi/blob/main/00-overview.md).

## Interrupt-parent resolution and generic registration boundary

Resolving ADT phandle `301989888` in that same JSON identifies
`/arm-io/aic`: `compatible = "aic,1"`, `device_type = "interrupt-controller"`,
and `#interrupt-cells = 1`. Thus the five `sgx` values are five one-cell AIC
source identifiers (134–138), not a GIC-style tuple and not META event-type
numbers. This resolves the interrupt-controller identity and cell format, but
not which source (if any) feeds the event-0 callback.

The kernelcache symbol table exposes the generic IOKit path names
`IODTInterruptControllerName` (`0xffffff80023a5e10`),
`IOService::lookupInterrupt` (`0xffffff80023b8ee4`),
`IOService::registerInterrupt` (`0xffffff80023b8f94`), and
`IOInterruptEventSource::interruptEventSource`
(`0xffffff80023d1ab0`). These are framework mechanisms, not evidence that AGX
uses them: the recovered AGX contains an `IOInterruptEventSource` factory call
with a different action and null provider, but no direct `registerInterrupt`
call. A read-only Ghidra xref query
against the existing `T7001.raw` project at those framework addresses returned
no xrefs, and function creation/decompilation failed because those addresses
are not mapped as code in that project. The existing AGX project query still
finds only the callback's vtable slot reference. So the generic registration
caller and AIC source-to-handler mapping remain untraced.

Linux's upstream T7001 binding describes the controller as
`apple,t7000-aic`/`apple,aic` with a three-cell Linux IRQ specifier; its AIC
binding defines cells as IRQ type, hardware IRQ number, and trigger flags.
That is a Linux translation layer, not the captured Apple ADT's one-cell
encoding, and the upstream T7001 SoC include does not list an SGX interrupt
assignment. Do not copy a Linux IRQ tuple into the native ADT interpretation.
References: [upstream T7001 DTS](https://gbmc.googlesource.com/linux/+/f79749a8e42b3a6dcb980e87f3ef752962b9f094/arch/arm64/boot/dts/apple/t7001.dtsi), [upstream Apple AIC driver](https://gbmc.googlesource.com/linux/+/434da42d7173bf097e9fab78ff97d51e8b74170d/drivers/irqchip/irq-apple-aic.c).

## Follow-up: ring drain to alive callback is now joined

The existing Ghidra project was reopened successfully with the local Java 21
runtime documented in `tools/ghidra/README.md`:
`/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home` and
`/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless` (Ghidra 12.1.4).
No project re-import or binary modification was needed.

An ADR reference scan of the preserved `AGX.raw` `__cstring` section located
the diagnostic strings `"Firmware event ring"`, `"Firmware alive event"`,
and `"Invalid interrupt index received"`. The first and third strings point
into routines `0xffffff800329bf40` (ring dump) and `0xffffff800329b71c`
(interrupt-index dispatch), respectively. Decompilation and the original
instruction stream establish this chain:

* `0xffffff8003287784` obtains an integer through its second argument's
  vtable slot `+0xe0`, subtracts the AGX object's 32-bit base at `+0xbc8`, and
  calls `0xffffff800329b71c`. The method owning that `+0xe0` slot is not yet
  identified, so this is an index adapter, not proof of a particular IOKit
  event-source class.
* The AGX property initializer at `0xffffff80032871f0` handles an
  `interrupts` property with five entries by storing `0x0000000500000004` at
  `+0xbbc`. The adapter subtracts the separate 32-bit field at `+0xbc8`; this
  initializer sets that field to 4 only in its nine-entry branch, not in the
  five-entry branch. The five-entry branch's effective subtraction base
  therefore depends on the object's prior initialization, which has not yet
  been established. The generic registration code is also still missing.
* `0xffffff800329b71c` sends normalized indices 0 and 4 through the firmware
  ring drain; indices 1, 2, and 3 go to the separate
  `0xffffff80032a1de8` path. Other values log an invalid index.
* The drain routine `0xffffff800329b7f8` handles firmware record types 0 and
  6 by invoking the firmware object's vtable slot `+0x1f0` with the record.
  Concrete firmware-class construction at `0xffffff800329d3bc` allocates a
  `0x5f8`-byte object and installs the table beginning at
  `0xffffff80032b3040`. Its `+0x1f0` entry is
  `0xffffff800329f6cc`, the previously identified alive callback. This is a
  direct static join: host ring record type 0 reaches the callback that sets
  the alive latch and wakes the `IOCommandGate`.

The five captured AIC source IDs remain `[134, 135, 136, 137, 138]` in ADT
array order. If the event callback receives property ordinals and the
five-entry object's `+0xbc8` field is zero, dispatch indices 0..4 correspond
to those IDs in order: 134 and 138 drain the firmware ring, while 135..137
take the separate META path. This mapping remains conditional: the parser,
subtraction, and five-way dispatch are static facts, but the object's effective
base and correspondence between returned index and ADT array ordinal are not
independently proven. No evidence identifies which of the two ring-drain
source IDs generates firmware alive event 0 in a particular boot.

This resolves the host-side event route from ring record to callback, but not
the firmware hardware producer: the firmware-side event ID 0 producer, the
hardware status/ack source, and the exact IOKit/AIC registration function are
still unknown. The generic `IOInterruptEventSource` symbols remain
unconnected; do not name `0xffffff8003287784` as its action solely because it
normalizes an interrupt index. Evidence: `ios81-agx-disasm.txt` around
`32871f0`, `3287784`, `329b71c`, `329b7f8`, and the `32b3040` vtable;
`ios81-postldr.c` around `329f6cc`; read-only Ghidra xrefs and
`DecompTo.java` results.

## Follow-up: event-ring structure and normalized-index limits

The offline disassembly makes the firmware event ring's host memory shape
explicit. The drain at `0xffffff800329b7f8` uses the AGX object's pointer at
`+0x208` for 40-byte (`0x28`) records. Its ring-state pointer at `+0x1e8` has
the consumer index at `+0`, a producer index at `+0x10`, and a 256-slot
wraparound: the consumer increments as `(consumer + 1) & 0xff`. The drain
snapshots the producer index, consumes records until the two indices match,
and issues `dmb ish` before publishing each consumer advance. Each record's
dispatch type is its first 32-bit word; handlers access the remaining words
at offsets `+8`, `+12`, `+16`, and `+24` as needed. For type 0, the record
address is passed to the firmware object's virtual method at vtable offset
`+0x1f0`; the object table resolves that slot to `0xffffff800329f6cc`. This
supports a host-side ring layout, not firmware-side allocation details or
producer ordering beyond what the host drain reads.

The `interrupts` property count branches in the initializer also pin down the
AGX normalization field more exactly than the earlier conditional description:
for the five-entry case, the 64-bit store at `+0xbbc` is followed by a zeroed
64-bit store at `+0xbc4`, so the subtraction base loaded at `+0xbc8` is zero.
For the nine-entry case, the store at `+0xbc4` leaves `+0xbc8` equal to four.
The separate callback at `0xffffff8003287784` invokes the second argument's
vtable slot `+0xe0` and subtracts this base. Therefore the five-entry case is
not base-ambiguous. If that virtual method yields the ordinal within the
five-entry property, normalized dispatch indices 0..4 map in array order to
AIC sources 134..138: 134 and 138 enter the ring drain, while 135..137 use the
META path. The ordinal interpretation is still unproven; the AIC cell values
themselves cannot be substituted as callback ordinals. No evidence selects
which of the two ring-drain sources carries alive event 0.

A fresh read-only Ghidra xref query using the documented Java 21/Ghidra 12.1.4
setup finds five data references to `0xffffff8003287784`, all in vtable data at
`0xffffff80032ad6a0`, `0xffffff80032af720`, `0xffffff80032b15a0`,
`0xffffff80032b3f30`, and `0xffffff80032b5370`; code references go only from
that routine to `0xffffff800329b71c`. This supports it being a virtual method
implemented in multiple tables, but does not reveal who constructs or registers
an interrupt source. The precise IOKit registration API/action, runtime source
index semantics, AIC-source-to-handler join, and firmware ring producer remain
unresolved. No firmware was executed and no device was accessed.

## Follow-up: `+0xe0` is `IOInterruptEventSource::getIntIndex`

The kernelcache symbol table identifies `IOInterruptEventSource::getIntIndex`
at `0xffffff80023d1db0`; its body is `ldr w0, [x0, #0x50]; ret`. The
`IOInterruptEventSource` vtable begins at `0xffffff8002492af0`; after its
two-word prefix, relative offset `+0xe0` contains exactly that function. Thus
the object passed as the second argument to `0xffffff8003287784` is accessed
through the exact `IOInterruptEventSource::getIntIndex` slot. Its return value
is the event source's stored interrupt index, resolving the earlier uncertainty
about the source accessor.

The AGX image also contains a direct factory call missed by the earlier
symbol-address xref scan. In `AGX.raw`, GOT file offset `0x2b370` contains
`0xffffff80023d1ab0`, the kernelcache address of
`IOInterruptEventSource::interruptEventSource`. Stub
`0xffffff80032a6240` loads GOT offset `+880` and branches through it; code at
`0xffffff80032858b4` calls this stub with owner `this`, action
`0xffffff8003285c94`, provider `NULL`, and index 0. This proves AGX creates an
`IOInterruptEventSource`, but this particular source does not register
`0xffffff8003287784`: the factory receives a different action and no provider.
No direct `IOService::registerInterrupt` call was found in AGX. The separate
five-entry `IOFilterInterruptEventSource` setup is resolved in the follow-up
below.

The consumer-side queue layout does not establish the producer's shared-memory
allocation or write order. No producer implementation has been joined
statically to this host ring; treat its record size and index behavior as host
drain observations only.

## Follow-up: five IOKit interrupt event sources are configured

A fresh pass over the original `ios81-agx-disasm.txt` together with the local
kernelcache symbol table resolves the interrupt setup loop in the AGX
initializer at `0xffffff8003285658` (decompiler output in
`artifacts/live/private/gpu-offline/gpc.c`). At `0xffffff80032858b4`, a
separate `IOInterruptEventSource` factory receives a different action,
`0xffffff8003285c94`, and a null provider/index 0; it is not the firmware-ring
dispatch path. The relevant loop calls `0xffffff80023d4d0c`, which the local
kernelcache `nm` table names
`IOFilterInterruptEventSource::filterInterruptEventSource(OSObject *, Action,
Filter, IOService *, int)`. The call arguments are, in ABI order:

| Argument | Evidence / meaning |
|---|---|
| owner | `this` (AGX accelerator) |
| action | `*(this->vptr + 0x780)` = `0xffffff8003287784` |
| filter | `*(this->vptr + 0x778)` = `0xffffff8003287750` |
| provider | initializer's `param2` |
| source index | loop index plus `this + 0xbc8` normalization base |

This is corroborated by the `AGXAcceleratorG4G_A0` vtable at
`0xffffff80032aefa0`: slot `+0x778` (entry at `0xffffff80032af718`) contains
`0xffffff8003287750`; slot `+0x780` (entry at `0xffffff80032af720`) contains
`0xffffff8003287784`. The latter action calls
`IOInterruptEventSource::getIntIndex` through slot `+0xe0`, subtracts the
normalization base, and dispatches through `0xffffff800329b71c` into the ring
drain for normalized indices 0 and 4. The filter at `0xffffff8003287750`
returns true after its fixed call at `0xffffff80032a63c0`, so it does not
discard the interrupt in the examined path.

For the captured five-entry `interrupts` property, the existing parser analysis
shows count 5 and normalization base 0. The setup loop therefore creates five
filter interrupt sources with source ordinals 0 through 4; the captured ADT
array stores AIC source IDs 134 through 138 in that order. Subject to the
property parser retaining array order (the static code reads the property and
passes successive integer indices), source ordinals 0 and 4 are the two ring
drain entries and ordinals 1–3 take the META path. This still does not tell us
which ring entry carries firmware event type 0 on a given boot.

The loop then calls the work loop's `addEventSource` method (kernelcache
symbol `IOWorkLoop::addEventSource(IOEventSource *)` at
`0xffffff80023cfe8c`) for each created filter source. This establishes
construction, provider/index configuration, and work-loop attachment. Do not
describe this AGX call as a direct `IOService::registerInterrupt` call: no such
direct call appears in the AGX image. The event-source framework and provider
own the subsequent enable/registration mechanics; the AIC's concrete
source-to-handler route and firmware-side ring producer remain outside the
joined evidence.

Public API cross-check: Apple's `IOService::registerInterrupt` documentation
defines its integer as the interrupt source index within the device, and the
upstream XNU `IOFilterInterruptEventSource` source documents the filter/action
split. These clarify API semantics, but the local iOS 8.1 kernelcache and AGX
instructions above are the version-specific evidence.
References: [Apple `registerInterrupt`](https://developer.apple.com/documentation/kernel/ioservice/1810691-registerinterrupt),
[XNU `IOFilterInterruptEventSource.cpp`](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/Kernel/IOFilterInterruptEventSource.cpp),
[XNU `IOWorkLoop.cpp`](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/Kernel/IOWorkLoop.cpp).

The host-side chain is now statically joined through source setup:

```text
ADT interrupt property -> five IOFilterInterruptEventSources -> action 3287784
  -> getIntIndex / normalize -> ring drain (indices 0, 4) -> type-0 alive callback
```

The bounds remain: ADT values are AIC source IDs, not event numbers; the index
adapter reduces them to property ordinals; no evidence yet identifies the
firmware producer, interrupt status/ack sequence, or which of the two ring
indices supplies event 0 in a particular run. This remains offline analysis;
no firmware was executed and no device was accessed.
