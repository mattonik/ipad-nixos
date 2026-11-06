# J81 G4G bootloader boundary

The local Orchard Linux source closes one part of the Apple/Linux comparison.
`pvr_fw_meta.c::configure_seg_mmu()` does not allocate a `META_BOOTLOADER`
layout object. It states that FW code uses a bootloader segment configured
before the META path, then emits the FW-data segment configuration into the
boot configuration area in the FW-code allocation. `pvr_fw.c` likewise maps
only `FW_CODE`, `FW_DATA`, `FW_COREMEM_CODE`, and `FW_COREMEM_DATA` entries.

Apple's J81 image has a slot-2 region at `0xc0000000` (56 bytes) and a
separate bootloader address `0xe1c0000000` in its host descriptor. The safe
conclusion is not that slot 2 should be relabelled `FW_CODE`; it requires an
explicit preconfigured-bootloader translation and boot-conf comparison.

This narrows the remaining adapter work: preserve the four packed Apple
segments for arithmetic validation, but keep slot 2 outside Linux allocation
accounting until the Apple boot descriptor is matched to Orchard's generated
boot configuration. No firmware bytes were copied or executed.
