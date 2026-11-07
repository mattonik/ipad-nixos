# J81 accelerator vtable `+0x210`

The ARM64 call site in `0xffffff800329e63c` resolves the unknown slot exactly:

```text
x0 = AGX accelerator object
x1 = mapped preparation-object base + four indexed offsets
x2 = index 0..3
```

The slot is invoked four times before the Apple LDR copy/verify routine with
four packed-view pointers and indices 0..3. The call shape suggests a
registration operation, but the callee is not proven from the call site. The
static base AGX table has `FUN_ffffff80032a0f30` at `+0x210` and the known
segment-config emitter `FUN_ffffff800329fea0` at `+0x248`; the table and
runtime-object caveats are documented in
[`2026-11-07-j81-segment2-vtable-slot-proof.md`](2026-11-07-j81-segment2-vtable-slot-proof.md).
The four offsets come from the initializer's host layout calculator
(`param + 0x524`).

This marks a boundary with Orchard: Apple passes four per-view addresses
through a dynamic accelerator method before loading the LDR, whereas Orchard
derives its FW-object addresses directly from layout entries and a single
FW-data allocation. A safe adapter must model only the observed call contract
and reject execution until Apple's address-domain policy is resolved.

No firmware was executed and no device state changed.
