# J81 segment-2 emitter versus preparation vtable slot

The new segment-config trace identifies `FUN_ffffff800329fea0` as a CPU-side
serializer. Its code emits register/value pairs into the host command buffer
at `param_1 + 0x5d8` and returns immediately for segment index 2. That alone
does not identify the runtime method used by the four registrations in
`FUN_ffffff800329e63c`.

The preserved static AGX table provides a direct cross-check. At table base
`0xffffff80032b3008`, the `+0xc0` entry is `FUN_ffffff800329d7d8`, matching the
descriptor-builder dispatch in the recovered AGX object. The same table's
entries relevant to the preparation call are:

| Slot | Table entry | Target |
|---:|---:|---|
| `+0x208` | `0xffffff80032b3210` | `FUN_ffffff800329f1a4` |
| `+0x210` | `0xffffff80032b3218` | `FUN_ffffff80032a0f30` |
| `+0x218` | `0xffffff80032b3220` | `FUN_ffffff800329f91c` |
| `+0x248` | `0xffffff80032b3250` | `FUN_ffffff800329fea0` |

The initializer at `0xffffff80032998d8` calls the receiver's `+0x208` slot;
the preparation routine at `0xffffff800329e63c` loads the receiver's `+0x210`
slot and invokes it with the mapped packed address and index 0..3. Under the
static table, that `+0x210` target is `FUN_ffffff80032a0f30`, **not** the
segment-config emitter at `+0x248`.

The body at `0xffffff80032a0f30` accepts `x0` and `x1`, walks the five records
starting at `0xffffff80032b32f0` alongside the receiver's map array at `+0x578`,
and calls opaque global thunks (`0xffffff80032a61a4` and
`0xffffff80032a645c`) with the supplied pointer and map objects. It does not
consume the third argument (`x2`), assign an AGX field, append register/value
pairs through `+0x5d8`, or issue a visible MMIO write. The thunks may have
side effects, so the body alone cannot establish that it is a no-op or rule
out an indirect mapping effect. It is incompatible with identifying the
known static `+0x210` implementation as the four-register segment-config
emitter.

The current evidence therefore separates three facts:

1. `FUN_...329e63c` passes four packed-view pointers plus indices 0..3 through
   a dynamic `+0x210` call.
2. The matching static AGX table candidate points `+0x210` to
   `FUN_...32a0f30`, while its `+0x248` points to the segment-config emitter.
3. `FUN_...329fea0` deliberately omits segment 2, but neither its callsite nor
   the owner of any existing segment-2 mapping is proven by this dispatch.

The static table is a strong receiver-table candidate: its `+0xc0` entry
matches the descriptor-builder dispatch, and its `+0x208` entry matches the
initializer's pre-preparation virtual call. The disassembly has one occurrence
each of the candidate targets in the table data and no recovered load/call
through receiver slot `+0x248`; `+0x248` is therefore present as a table
entry, but no callsite in this image is established. No alternate static
table entry pointing to `FUN_...329fea0` at `+0x210` was found in the
preserved AGX disassembly. The runtime vptr is still not proven by a
constructor store or dynamic-type provenance, so an override in another
kext/object remains possible.

Thus the prior claim that the four `+0x210` calls are known setter/registration
operations must remain a call-site interpretation, not resolved callee
semantics. Static evidence rules out equating `+0x210` with the known `+0x248`
emitter for the best-matching base table; it does not prove which method
actually ran at runtime.

## What reaches the boot/config output

In `FUN_...329e63c`, the return from `+0x210` is discarded. The routine then
calls the CPU LDR parser `FUN_...329fbe8`. That parser handles Config records
by appending their explicit register/value pairs to the host buffer at
`+0x5d8`; the segment emitter at `+0x248` is not called there. After parsing,
`FUN_...329e63c` appends zero terminators and uses the separate `+0x140`
translation method to write translated root/preparation pointers into
`+0x5d8`. Therefore the known command stream has these sources: parsed LDR
Config records, terminators, and translated descriptor pointers. The four
`+0x210` calls are not shown writing that stream in the best-matching static
implementation. The traced preparation routines do not execute the emitted
pairs as MMIO; the later META consumer remains unresolved.

## Bootloader cross-check

The local Orchard Rogue implementation in
`artifacts/live/private/gpu-offline/orchard-g5p-transport.patch`,
`g5p_make_boot_config()`, independently treats slot 2 as a special
bootloader segment. It emits only the `reg + 12` high-address marker for that
slot; the other segments get the ordinary four-pair tuple. The public Rogue
headers/source cited in
`2026-11-07-j81-segment2-config-write-trace.md` identify the default META
bootloader address `0x40000000` and device-virtual heap base `0xe1c0000000`.
These are useful ABI comparators, but do not resolve Apple's dynamic
`+0x210` target or prove that J81's 56-byte slot-2 record has the same
preconfigured mapping.

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
