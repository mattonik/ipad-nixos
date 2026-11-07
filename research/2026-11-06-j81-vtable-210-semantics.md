# J81 accelerator vtable `+0x210`

The ARM64 call site in `0xffffff800329e63c` resolves the unknown slot exactly:

```text
x0 = AGX accelerator object
x1 = mapped preparation-object base + four indexed offsets
x2 = index 0..3
```

The slot is invoked four times before the Apple LDR copy/verify routine with
four packed-view pointers and indices 0..3. Constructor evidence identifies
the receiver as `AGXMetaFirmware` with installed vptr `0xffffff80032b3040`;
address-point slot `+0x210` is `FUN_ffffff800329fea0`, the segment-config
emitter. Earlier group-start indexing incorrectly assigned the unrelated
`FUN_ffffff80032a0f30` to this runtime slot. See
[`2026-11-07-j81-staging-map-runtime-consumer.md`](2026-11-07-j81-staging-map-runtime-consumer.md).
The four offsets come from the initializer's host layout calculator
(`param + 0x524`).

This marks a boundary with Orchard: Apple passes four per-view addresses
through a dynamic accelerator method before loading the LDR, whereas Orchard
derives its FW-object addresses directly from layout entries and a single
FW-data allocation. A safe adapter must model only the observed call contract
and reject execution until Apple's address-domain policy is resolved.

No firmware was executed and no device state changed.
