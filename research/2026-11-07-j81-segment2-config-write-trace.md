# J81 segment-config emitter and command-buffer boundary

`FUN_ffffff800329e63c` allocates and maps an aligned firmware-preparation
object with selector `0x70007`, then points `param_1[0xbb]` (byte offset
`+0x5d8`) at the mapped host buffer plus `0x200`. It calls an unresolved
accelerator vtable method at `+0x210` four times with packed offsets and
indices 0..3, then runs `FUN_ffffff800329fbe8`. That CPU-side parser copies and
verifies LDR records; Config records append register/value pairs through the
same `+0x5d8` output pointer. The routine later appends terminators and puts
translated buffer/range addresses in the preparation descriptor. The later
descriptor consumer/start handoff remains unresolved.

The G4G image has a 56-byte segment-2 load at raw LDR address `0xc0000000`.
Apple's host copy path masks its global-alias bit, producing normalized
address `0x40000000`; the offline layout puts it at candidate staging offset
`0x13000`. Thus slot 2 has bytes in the host-side
`0x70007` preparation object and is one of the four packed views passed through
the `+0x210` registration call. Its exact device-visible address and any
preconfigured bootloader mapping are still unknown. The separate
`0x90007` resource-registration loop handles four auxiliary records and skips
its fifth core-MMIO record; it does not establish the mapping of this packed
segment-2 image region.

The iOS 8.1 AGX disassembly contains the segment-config emitter at
`0xffffff800329fea0`. It takes the segment index in `w2`. For every index
other than 2, it serializes four register/value pairs through the output pointer
at object offset `+0x5d8`:

| Register | Serialized value |
|---|---|
| `0x04850000 + index * 0x10` | source segment flags OR `0xf02` |
| `+4` | source segment size minus one (bounded to `0xfff` for small sizes) |
| `+8` | low 32 bits of the segment address |
| `+12` | high address bits combined with provider cache/context bits |

For index 2, the very first branch (`cmp w2, #2; b.eq 0xffffff800329ff24`)
jumps directly to the return. This implementation emits no tuple for any of
the four `0x04850020..0x0485002c` registers. It writes a host-side command
buffer; it does not itself perform MMIO.

The disassembly's static table word at `0xffffff80032b3250` points to this
function. The firmware-preparation routine separately calls a vtable method at
`+0x210` four times, with the four packed offsets and indices 0..3, but that
runtime target is unresolved. Do not equate it with this emitter on current
evidence. The established finding is narrower: Apple contains a segment-config
emitter implementation that deliberately omits segment 2; its callsite and the
owner of any preexisting mapping remain unproven.

The J81 descriptor builder independently stores `0xe1c0000000` at descriptor
offset `+0x210` (`ios81-thread-use.c`, `FUN_ffffff800329d7d8`), while the
G4G image's normalized slot-2 address is `0x40000000`. Those values match public Rogue
defaults (`RGXFW_BOOTLDR_META_ADDR` and `RGXFW_BOOTLDR_DEVV_ADDR`), but do not
prove Apple's `+0x210` maps the packed image bytes to that address. The
segment-emitter method's branch is a useful lead, not proof that this method
is the runtime `+0x210` target or that its serialized tuple is consumed.

The related J81 address helper at `0xffffff800329ff28` applies an address-class
prefix and translation constant to a supplied address. It does not program the
segment registers or identify the physical backing. The provider's final
address-domain behavior remains subject to the custom descriptor `+0xa8`
boundary documented in `2026-11-06-j81-descriptor-address-limit.md`.

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` around
`0xffffff800329fea0..0xffffff800329ff50`,
`ios81-thread-use.c`, `ios81-memory-registration.c`, and
`2026-11-07-j81-resource-table-and-descriptor-dispatch.md`. Rogue comparator:
[1.17 `rgx_meta.h`](https://chromium.googlesource.com/chromiumos/third_party/kernel/+/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h).
No firmware or hardware access was performed.
