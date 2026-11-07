# J81 META boot segment: public startup path and Apple-side evidence

This follow-up traces what the public Rogue host does with its preconfigured
META bootloader segment, then checks the corresponding J81 firmware-start
path. It distinguishes the boot PC selection from segment-MMU programming.

## What public Rogue sets at startup

The public 1.17 Rogue start routine selects `RGXFW_BOOTLDR_META_ADDR` as META
thread 0's PC via the META slave port, ORing in the global-range bit; it then
enables minimal encoding and the META thread
([`rgxstartstop.c`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/refs/heads/chromeos-4.19/drivers/gpu/drm/img-rogue/1.17/rgxstartstop.c), lines 160–184). Earlier in that startup sequence it initializes clocks, META wrapper, and BIF before releasing the firmware processor from reset (lines 887–975).

The header identifies `RGXFW_SEGMMU_BOOTLDR_ID` as `2` and aliases
`RGXFW_SEGMMU_TEXT_ID` to it. The older 1.9 public image utility also declares
the bootloader/code segment at `0x40000000`, but its `RGXFWConfigureSegMMU()`
loop configures only the separate DATA segment (lines 246–287), not ID 2.
This confirms that the omitted slot is the Rogue bootloader/code segment in
those sources, rather than an arbitrary segment that happens to share an
address. See
[`rgx_meta.h`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h)
and
[`rgxfwimageutils.c`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/refs/heads/firmware-fizz-10139.117.B-chromeos-4.4/drivers/gpu/drm/img-rogue/1.9/rgxfwimageutils.c).

This routine does **not** program segment-2 base/limit/output registers. The
Linux firmware preparation code separately documents the bootloader segment
as already configured "on boot" and emits segment-MMU tuples only for the
firmware data entry (`pvr_fw_meta.c`, lines 943–964, linked in the prior
cross-check). The public code makes the two operations distinct: host chooses
the boot PC and starts META; it relies on a preexisting bootloader mapping.
It does not identify whether that mapping comes from META reset defaults,
ROM, or earlier platform firmware. The phrase "on boot" is not enough to
claim a particular reset value or reset-retention behavior.

## J81-side sequence found in the preserved iOS 8.1 AGX image

Apple's AGX GPC control path contains a direct write of `0x40000000` to the
first word of its mapped command area (`FUN_ffffff80032a1f84`). That helper is
called during GPC firmware handshake/start paths, including
`FUN_ffffff800329eb88`, `FUN_ffffff800329f024`, and
`FUN_ffffff800329f710` (disassembly callsites and recovered code in
`ios81-gpc-helpers.c` / `gpc-link.c`). This is consistent with Apple's start
protocol using the same META boot address, but the helper boundary alone does
not prove that the command word is a PC value. It is not a write to
`0x04850020..0x0485002c` and does not establish the segment mapping.

The J81 preparation routine still emits no visible segment-2 tuple, and its
best static `+0x210` table candidate remains an unresolved helper with opaque
mapping thunks. The known descriptor field `0xe1c0000000` and normalized
firmware segment-2 load address `0x40000000` (raw LDR destination
`0xc0000000`) match public Rogue's bootloader defaults,
but no local disassembly located an earlier J81 write of the slot-2
segment-MMU registers, nor evidence that those registers are populated by
reset/ROM. Apple's boot PC selection is the closest direct analogue found;
the actual META address translation remains unproven.

## Implication

Treat slot 2 as a boot-owned address window in the working model, not as a
known AGX setup operation. Existing data supports the PC address and a public
Rogue pattern of leaving the boot segment preconfigured. It does **not** yet
support implementing a J81 slot-2 map, assuming a reset default, or deciding
which software component provisions it. To close that gap offline, recover
the exact J81 META segment-2 register writes or reset-state description from
an Apple boot-stage/kernel path, or establish the `+0x210` runtime target and
its opaque thunk effects. Hardware probing is outside this evidence.

Evidence: local `ios81-gpc-helpers.c`, `gpc-link.c`, and
`ios81-agx-disasm.txt` around `0xffffff800329eb88`,
`0xffffff800329f024`, `0xffffff800329f710`, and
`0xffffff80032a1f84`; public [`rgxstartstop.c`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/refs/heads/chromeos-4.19/drivers/gpu/drm/img-rogue/1.17/rgxstartstop.c)
and prior public-source citations in
[`2026-11-07-j81-segment2-boot-provisioning-crosscheck.md`](2026-11-07-j81-segment2-boot-provisioning-crosscheck.md).
No hardware or firmware execution was performed.
