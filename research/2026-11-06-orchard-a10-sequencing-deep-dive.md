# Orchard A10 sequencing versus J81

I reviewed Orchard commit `b5e37693bb1246ce566406a205ae0ca834cdc18e9`
(`kernel: the A10 GPU in drm/imagination`) and compared its power-on path with
the J81 captures.

## What the A10 driver actually requires

The A10 implementation is not just a register shim. Before any RGX access it:

1. maps a 1 MiB firmware window and a coherent heap;
2. programs the window into both Fender (`+0x200c`, 4-byte stride) and the A7-IOP
   (`+0x8`, 8-byte stride), then enables the IOP window at `+0x38`;
3. enables Fender run at `+0x2048`;
4. boots Apple RTKit and starts endpoints `0x20` and `0x21`;
5. forces Fender state 0 when a previous state is nonzero;
6. requests a nonzero performance state and waits for the acknowledged state;
7. only then builds the Apple firmware layout and waits for the firmware's
   shared-memory ready flag.

The A10 driver therefore has two separate prerequisites that our J81 probes do
not have: a live coprocessor transport and a firmware-owned shared-memory
contract. Its `gfx-kf`/A7-IOP node is not optional plumbing.

## J81 comparison: what is and is not missing

Test4 reached PMGR `0x3ff`, completed the exact 66 selector 9/10 writes,
reached GPC state 1/control `0x40000000`, and then stalled on the first RGX
identity read at `0x201000020`. This rules out those replayed writes plus the
tested GPC setup as sufficient for a completed read; it does not identify the
cause.

The matching iOS 8.1 G4G start trace now identifies a concrete earlier
difference: before the GPC writes, Apple calls provider slots `+0x560(1,0)`
and `+0x568(1,&local,0)`; only after GPC setup does its identity matcher read
RGX `+0x20` then `+0x18`. Test4 replayed the selector stores and generic PMGR
cycle but did not execute those provider callbacks or their software-side
state transitions. This is a falsifiable sequence gap, not proof that it caused
the hang. The callback's SoC-busy/display work is separately conditional and
its runtime inputs are not captured; see
`2026-11-07-j81-core-read-missing-apple-dispatch.md`.

Do not infer an A10 RTKit prerequisite from the A10 driver's order. The A10
T8010 path boots its `gfx-kf` A7-IOP and RTKit before its first RGX access, but
the J81 iOS 8.1 G4G trace reaches its first identity matcher before the later
firmware-object hold/start path. The A10 protocol is therefore not evidence
that A8X needs the same coprocessor transport or an alive message to make this
pre-firmware identity read work. Conversely, A10's Fender state register and
successful core-ID read are T8010/G9P evidence, not a J81 register recipe.

The useful comparison is limited to sequencing discipline: both paths gate RGX
access on platform setup, but the specific blocks and ordering differ. No
J81 firmware/alive step is established as a missing prerequisite for the
first identity read; the provider callbacks immediately before GPC remain the
known unexecuted Apple sequence in test4, with causality unresolved.

## Consequence for implementation

Do not port `pvr_apple.c` or its A10 firmware filename to J81. Keep the A10
RTKit/window contract separate from J81's pre-ID G4G path. Offline work can
continue tracing the J81 firmware host contract for the later firmware start,
but that is downstream of the current first-read hang and does not yet justify
another RGX read or render attempt.

Source checked locally; no firmware bytes or hardware access were added.

## J81-specific host contract found offline

The 8.1 `AGXG4G` preparation routine at `0xffffff800329e63c` takes a
different route. It maps an Apple memory view with selector `0x70007`, obtains
the returned view offset through its `+0x80` method, and calls the accelerator
vtable's `+0x210` hook four times with the packed firmware-view offsets. It
then copies/verifies the LDR records and appends the six-word boot descriptor
and translated object addresses.

That is the concrete reason a generic META loader cannot be enabled yet: the
J81 path needs an Apple view mapper and the `+0x210` registration hook before
the firmware can see the copied image. The existing layout audit proves that
the records fit candidate allocations, but not that those allocations are
visible in the required Apple views.

The disassembly also makes the callback ABI explicit: the mapped view's `+0x80`
returns the runtime base, and vtable `+0x210` is called as
`(accelerator, base + packed_offset, index)` for indices 0 through 3. This is a
registration callback, not an RGX MMIO access; it runs before LDR copy/verify
and before the boot-descriptor writes.
