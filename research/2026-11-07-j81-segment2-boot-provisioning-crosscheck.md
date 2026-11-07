# J81 segment-2 boot provisioning cross-check

This follow-up checks whether public Rogue META firmware code explains the
missing J81 segment-2 tuple. It gives a strong architectural comparator, but
does not resolve Apple's runtime vtable owner or prove the A8X boot mapping.

## New public-source evidence

The current Linux Rogue META implementation in
[`pvr_fw_meta.c`](https://git.zx2c4.com/linux-rng/tree/drivers/gpu/drm/imagination/pvr_fw_meta.c?id=6dfafbd0299a60bfb5d5e277fdf100037c7ded07)
separates bootloader/code from the normal firmware data segment. Its
`configure_seg_mmu()` comment says firmware code uses the bootloader segment
"which is already configured on boot"; its loop only calls
`configure_seg_id()` for the `FW_DATA` layout entry (lines 943–964). The
four-register writer is explicit at lines 902–923. This is direct evidence
that at least one Rogue META generation expects a boot-provided segment and
does not reprogram it in the host's segment setup.

The older public 1.9 image utility makes the distinction concrete: the META
code segment table has one entry at `RGXFW_BOOTLDR_META_ADDR` (`0x40000000`)
and labels it "Bootldr and Code"; data is a distinct segment entry
(`rgxfwimageutils.c`, lines 78–87). The public 1.17 header independently
defines `RGXFW_BOOTLDR_META_ADDR` as `0x40000000`, and defines the bootloader
configuration area at dword offset `0x80` ([`rgx_meta.h`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/f66be639e83bf9b6fe6e57d5fc84029958022f3c/drivers/gpu/drm/img-rogue/1.17/rgx_meta.h), lines 315–326).

## J81 relationship and limit

The J81 G4G image has its 56-byte segment-2 load at raw address `0xc0000000`.
Apple's copy path masks the global-alias bit, normalizing it to `0x40000000`;
the offline layout model places that one-segment extent at candidate staging
offset `0x13000`. Apple's known segment-config emitter
returns before writing any segment-2 tuple. That pairing is consistent with
the public Rogue design: a slot-2 bootloader/code mapping could be installed
before AGX prepares the firmware, while the host emits tuples for other
segments. It makes the boot-preprovision hypothesis more plausible than
assuming that Apple forgot slot 2.

This is still a cross-generation ABI comparison. Apple runtime dispatch is
resolved: the installed `AGXMetaFirmware` `+0x210` slot calls the emitter, and
that emitter skips slot 2. The owner/source of any earlier boot mapping and
the A8X firmware-visible mapping remain unknown. The public Linux comment
describes Rogue behavior, not Apple's boot chain. No J81 register write or
reset-state evidence for slot 2 was found in this pass. Do not infer a Linux
implementation or copy its setup sequence into J81 from this evidence.

## Dispatch status

The runtime `+0x210` target is `FUN_ffffff800329fea0`, proven by the installed
vptr/address point `0xffffff80032b3040` and table word at `0xffffff80032b3250`.
It appends segment tuples for indices 0, 1 and 3 and returns for index 2. The
different `FUN_ffffff80032a0f30` result came from incorrectly indexing the
vtable group start. Neither the resolved emitter nor the static image shows
who established slot 2's mapping.

Evidence: `artifacts/live/private/gpu-offline/firmware-prepare.c`,
`firmware-layout.c`, and `ios81-agx-disasm.txt` at
`0xffffff800329e63c..0xffffff800329e774`,
`0xffffff80032a0f30..0xffffff80032a102c`,
`0xffffff800329fea0..0xffffff800329ff24`, and
`0xffffff80032b3210..0xffffff80032b3250`; public source links above and
[`rgxfwimageutils.c`](https://chromium.googlesource.com/chromiumos/third_party/kernel/%2B/refs/heads/firmware-fizz-10139.117.B-chromeos-4.4/drivers/gpu/drm/img-rogue/1.9/rgxfwimageutils.c).
No firmware execution or hardware access was performed.
