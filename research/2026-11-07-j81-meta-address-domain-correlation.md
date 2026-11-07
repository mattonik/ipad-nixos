# J81 META address-domain correlation

The extracted G4G image gives three defensible address-domain facts:

* segment 0 occupies `0x10000000..0x1000f000` and thread 0 points at
  `0x10000000`;
* segment 1 occupies `0x20000000..0x20004000` and thread 1 points at
  `0x20000000`;
* segment 2 is a 56-byte load at raw address `0xc0000000`, while segment 3
  uses raw alias addresses beginning at `0xe0001000`.

Apple's parser uses the low 31 bits as the segment-relative address, so these
normalize to `0x40000000` and `0x60001000`. The first normalized address
matches Rogue's META bootloader PC; this normalization is observed in the
host copy path, but the separate device-visible address conversion is not
recovered.

This matches the ordinary FW-data roots used by the Orchard META layout for
segments 0 and 1, and it supports treating those two slots as address-domain
compatibility candidates. It does **not** resolve segment 3 ownership: the
image uses a global/alias address class there, so it may be a separate data
object or an alias into code/data.  Segment 2 remains the special
`META_BOOTLOADER` slot; its arithmetic location alone is not enough to map it
through Linux's normal FW-data path.

The result narrows the Linux adapter boundary without claiming execution:
preserve segment 0 and segment 1 as separate FW-data candidates, keep segment
2 as an explicit preconfigured-bootloader candidate, and leave segment 3
unresolved until the Apple descriptor consumer identifies its ownership and
address-view conversion.

Evidence: `gpu_g4g_apple_model.py` output for
`artifacts/live/private/gpu-offline/g4g81-image.bin`, the extracted thread
records, and Orchard's `g5p_make_boot_config()` segment table. No firmware or
hardware access was performed.
