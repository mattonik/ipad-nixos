# J81 META slot 2: raw alias and host staging

The LDR destination and the boot PC use different address views. In the
preserved G4G image, slot 2's only load record targets raw META address
`0xc0000000` and contains 56 bytes. The report generator assigns it slot index
2 with address class `global-alias`; it is not a raw `0x40000000` load.

Apple's host preparation path explains the arithmetic. `FUN_ffffff800329fa14`
groups the high-address LDR ranges by bits 29–30 and tracks their low 31-bit
bounds. `FUN_ffffff800329fbe8` selects group 2 for `0xc0000000`, masks the
address with `0x7fffffff`, then computes the copy offset relative to that
group's minimum. For this one-record range, the normalized start is
`0x40000000` and the relative offset is zero. The payload is copied and
byte-compared through the CPU mapping retained at AGX `+0x570`.

The offline layout model packs slot 0 (60 KiB), slot 1 (16 KiB), slot 2
(4 KiB), then slot 3 (4 KiB), placing slot 2 at candidate staging offset
`0x13000` in the preparation allocation. That is a layout-model result, not a
physical address: `FUN_ffffff800329e63c` allocates an aligned memory descriptor,
maps it, then drops the temporary descriptor while retaining the mapping.
The available call/import artifacts do not expose the allocator's backing
page list, contiguity, or DART/device address.

This yields a useful, limited bridge between the image and the bootloader
convention: raw `0xc0000000` normalizes to `0x40000000`, the same META boot PC
defined by public Rogue. Public Rogue separately pairs that META address with
device virtual address `0xe1c0000000` and treats the bootloader/code segment as
already configured on boot. The J81 descriptor also contains
`0xe1c0000000`, but this cross-match does not prove that J81 programs the same
translation or that slot 2 points at the retained preparation allocation.
Apple's `+0x210` dispatch receives per-slot mapped addresses and resolves to
the segment-config emitter, which skips index 2 before appending a tuple. No
physical backing or device-visible slot-2 consumer was identified.

Evidence: `tools/gpu_ldr_inspect.py`'s metadata-only report for
`artifacts/live/private/gpu-offline/g4g81-image.bin` (record address, length,
class and slot index); `firmware-layout.c` (`FUN_...329fa14`,
`FUN_...329fbe8`); `firmware-prepare.c` (`FUN_...329e63c`);
`ios81-thread-use.c` (descriptor bootloader field); and the public
[`rgx_meta.h`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h),
[`rgxinit.c`](https://android.googlesource.com/kernel/mediatek/%2B/android-mtk-3.18/drivers/staging/imgtec/rogue/rgxinit.c), and
[`pvr_fw_meta.c`](https://gbmc.googlesource.com/linux/%2B/92a09c47464d040866cf2b4cd052bc60555185fb/drivers/gpu/drm/imagination/pvr_fw_meta.c).
All evidence is static or metadata-only; no firmware execution or hardware
access was performed.
