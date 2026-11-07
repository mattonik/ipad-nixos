# J81 segment-2 emitter versus preparation vtable slot

The segment-config trace identifies `FUN_ffffff800329fea0` as a CPU-side
serializer. Its code emits register/value pairs into the host command buffer
at `param_1 + 0x5d8` and returns immediately for segment index 2. Constructor
evidence establishes it as the runtime `+0x210` target called four times by
`FUN_ffffff800329e63c`.

The preserved AGX vtable group provides a direct cross-check. At group base
`0xffffff80032b3008`, the `+0xc0` entry is `FUN_ffffff800329d7d8`, matching the
descriptor-builder dispatch. These are group-relative positions, not the
installed full-object address point's slots:

| Group-relative offset | Table entry | Target |
|---:|---:|---|
| `+0x208` | `0xffffff80032b3210` | `FUN_ffffff800329f1a4` |
| `+0x210` | `0xffffff80032b3218` | `FUN_ffffff80032a0f30` |
| `+0x218` | `0xffffff80032b3220` | `FUN_ffffff800329f91c` |
| `+0x248` | `0xffffff80032b3250` | `FUN_ffffff800329fea0` |

The initializer at `0xffffff80032998d8` calls the receiver's `+0x208` slot.
The constructor-installed full-object address point is
`0xffffff80032b3040` (group base `0x32b3008` plus `0x38`), so this call
resolves to table word `0xffffff80032b3248` and target
`FUN_ffffff800329d0c4`, not `FUN_ffffff800329f1a4`. The latter is only the
group-base-relative `+0x208` candidate. Its actual body at `0x329f1a4` must
not be attributed to the initializer. The preparation routine at
`0xffffff800329e63c` loads the installed object's `+0x210` slot and invokes
it with the mapped packed address and index 0..3. Its word at
`0xffffff80032b3250` targets `FUN_ffffff800329fea0`; the old group-start
calculation (`0x32b3008 + 0x210`) incorrectly selected
`FUN_ffffff80032a0f30`.

The actual `FUN_ffffff800329d0c4` body stores constants (`0x180`, `0x400`,
`0xc0`, and `0x40`) into fields of its receiver. The preserved body has no
segment-register address or MMIO operation, so this correction does not
identify who preconfigures segment 2.

The separate group-start candidate `FUN_ffffff80032a0f30` accepts `x0` and `x1`, walks the five records
starting at `0xffffff80032b32f0` alongside the receiver's map array at `+0x578`,
and calls opaque global thunks (`0xffffff80032a61a4` and
`0xffffff80032a645c`) with the supplied pointer and map objects. It does not
consume the third argument (`x2`), assign an AGX field, append register/value
pairs through `+0x5d8`, or issue a visible MMIO write. The thunks may have
side effects, so the body alone cannot establish that it is a no-op or rule
out an indirect mapping effect. It is incompatible with identifying the
known static `+0x210` implementation as the four-register segment-config
emitter.

The corrected evidence establishes three facts:

1. `FUN_...329e63c` passes four packed-view pointers plus indices 0..3 through
   a dynamic `+0x210` call.
2. The installed `AGXMetaFirmware` address point maps `+0x210` to
   `FUN_...329fea0`, which emits the segment tuples.
3. The actual calls include index 2, which immediately returns without its
   tuple. Any existing segment-2 mapping's source and owner remain unknown.

The constructor-installed address point and slot are directly established.
`FUN_...32a0f30`'s group-start behavior is not evidence about this called
runtime method.

The four `+0x210` calls resolve to the known emitter. The index-2 early return
means they do not write slot-2 configuration to the host command stream. This
does not identify an earlier/preconfigured mapping, its device-visible target,
or prove that the command stream is later consumed by hardware.

## What reaches the boot/config output

In `FUN_...329e63c`, the return from `+0x210` is discarded. The routine then
calls the CPU LDR parser `FUN_...329fbe8`. That parser handles Config records
by appending their explicit register/value pairs to the host buffer at
`+0x5d8`; the emitter output is already in that buffer from the earlier
`+0x210` calls. After parsing,
`FUN_...329e63c` appends zero terminators and uses the separate `+0x140`
translation method to write translated root/preparation pointers into
`+0x5d8`. Therefore the known command stream has these sources: parsed LDR
Config records, tuples emitted for indices 0, 1 and 3, terminators, and
translated descriptor pointers. The traced preparation routines do not execute
the emitted pairs as MMIO; the later META consumer remains unresolved.

## Bootloader cross-check

The local Orchard Rogue implementation in
`artifacts/live/private/gpu-offline/orchard-g5p-transport.patch`,
`g5p_make_boot_config()`, independently treats slot 2 as a special
bootloader segment. It emits only the `reg + 12` high-address marker for that
slot; the other segments get the ordinary four-pair tuple. The public Rogue
headers/source cited in
`2026-11-07-j81-segment2-config-write-trace.md` identify the default META
bootloader address `0x40000000` and device-virtual heap base `0xe1c0000000`.
These are useful ABI comparators, but do not prove that J81's 56-byte slot-2
record shares the public generation's preconfigured mapping contract.

The public Cascadia A5/SGX543 source reviewed elsewhere in this repository
concerns that generation's graphics register banking and boot order; it does
not expose an A8X/Rogue META segment-2 loader contract. It is therefore a
negative portability check, not support for copying an SGX slot or register
rule into J81 (see
[`2026-11-07-j81-gpc-core-read-caller-boundary.md`](2026-11-07-j81-gpc-core-read-caller-boundary.md#comparison-with-orchard-and-cascadia)).

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` at
`0xffffff800329e63c..0xffffff800329e774`,
`0xffffff800329fea0..0xffffff800329ff24`,
`0xffffff80032a0f30..0xffffff80032a102c`, and
`0xffffff80032b3008..0xffffff80032b3258`; decompilation in
`ios81-init-allocation.c`, `ios81-thread-use.c`, and `firmware-prepare.c`.
No firmware or hardware access was performed.
