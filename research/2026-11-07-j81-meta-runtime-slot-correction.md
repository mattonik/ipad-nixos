# J81 META runtime slot correction and address translator

The iOS 8.1 `AGXMetaFirmware` constructors install vptr/address point
`0xffffff80032b3040`, which is `0x38` bytes into the group whose base is
`0xffffff80032b3008`. This offset matters when reading virtual slots:

| Runtime slot | Address point + slot | Table target | Role observed |
|---:|---:|---:|---|
| `+0x140` | `0xffffff80032b3180` | `FUN_ffffff800329ff28` | META address translation |
| `+0x208` | `0xffffff80032b3248` | `FUN_ffffff800329d0c4` | Stores fixed resource-geometry fields |
| `+0x210` | `0xffffff80032b3250` | `FUN_ffffff800329fea0` | Emits segment-config tuples, except index 2 |

The group-start `+0x208` word at `0xffffff80032b3210` points to
`FUN_ffffff800329f1a4`; that is not the installed object's runtime `+0x208`
method. The initializer at `0xffffff80032998d8` calls the object's slot, so
its target is `FUN_...329d0c4`. That body stores `0x180`, `0x400`, `0xc0`, and
`0x40` at receiver offsets `+0x18`, `+0x20`, `+0x28`, and `+0x30..+0x50`.
It contains no segment-2 register write. The earlier note's group-relative
table remains valid as a table dump, but its row must not be read as a
runtime vtable slot mapping; the correction is recorded in
[`2026-11-07-j81-segment2-vtable-slot-proof.md`](2026-11-07-j81-segment2-vtable-slot-proof.md).

## Exact `+0x140` arithmetic

At `0xffffff800329ff28`, the instruction sequence constructs
`0xffffff1e40000000`, adds it to `arg1`, then ORs one of two region prefixes.
Since `0xffffff1e40000000` is the two's-complement value of
`-0xe1c0000000`, the operation is:

```text
result64 = (arg1 - 0xe1c0000000) | region
region   = 0xc0000000 if arg2 == 0 or (this + 0x5cc) != 0
           0x40000000 otherwise
```

The preparation caller at `0xffffff800329e63c` stores the result into 32-bit
init/config fields, so those fields contain `result64 & 0xffffffff`. As an
arithmetic example only, if `arg1` equals `0xe1c0000000 + 0x13000`, the
result is `0xc0013000` on the `0xc0000000` branch or `0x40013000` on the
`0x40000000` branch. `0x13000` is the offline candidate packed staging offset
for slot 2; the example does not prove that this is the actual translator
input, that either region is mapped, or that slot 2 is backed by this staging
allocation.

The call sites in `firmware-prepare.c` use this translator to encode existing
mapped addresses and parsed offsets into host-side init/config structures.
They do not write the META segment registers. The resulting root pointer and
translated fields reach the host-prepared output at `param_1[0xf] + 0x6c`
and `+0x70`, and the command stream through `param_1 + 0x5d8`; no downstream
consumer that programs segment 2 or consumes these particular fields was
resolved in the available static trace. The segment emitter at `+0x210`
still returns before the slot-2 tuple.

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff800329ff28..0xffffff800329ff50`, the installed-vptr stores at
`0xffffff800329d3bc..0xffffff800329d480`, the table words at
`0xffffff80032b3180`, `0xffffff80032b3248`, and `0xffffff80032b3250`, plus
`firmware-prepare.c` and `ios81-postldr.c`. No firmware was executed and no
hardware was accessed.
