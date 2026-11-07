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
callback registration. The recovered AGX disassembly has no direct calls to
the kernelcache's `IOInterruptEventSource` factory or `IOService::registerInterrupt`
symbols. Indirect framework paths remain possible and are not resolved here.

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
