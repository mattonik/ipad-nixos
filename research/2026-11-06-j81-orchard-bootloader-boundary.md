# J81 G4G bootloader boundary

The local Orchard Linux source closes one part of the Apple/Linux comparison.
`pvr_fw_meta.c::configure_seg_mmu()` does not allocate a `META_BOOTLOADER`
layout object. It states that FW code uses a bootloader segment configured
before the META path, then emits the FW-data segment configuration into the
boot configuration area in the FW-code allocation. `pvr_fw.c` likewise maps
only `FW_CODE`, `FW_DATA`, `FW_COREMEM_CODE`, and `FW_COREMEM_DATA` entries.

Apple's J81 image has a 56-byte slot-2 region at `0x40000000` in the META
address domain and `0xe1c0000000` in its host descriptor. Public Rogue code
identifies these as a bootloader META address and firmware heap/device virtual
address, respectively; see [the descriptor investigation](2026-11-07-j81-resource-table-and-descriptor-dispatch.md#descriptor-handoff-and-limit).
That comparison does not prove J81's mapping. The safe
conclusion is not that slot 2 should be relabelled `FW_CODE`; it requires an
explicit preconfigured-bootloader translation and boot-conf comparison.

This narrows the remaining adapter work: preserve the four packed Apple
segments for arithmetic validation, but keep slot 2 outside Linux allocation
accounting until the Apple boot descriptor is matched to Orchard's generated
boot configuration. No firmware bytes were copied or executed.
