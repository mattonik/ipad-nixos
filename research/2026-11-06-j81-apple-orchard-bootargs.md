# J81 Apple/Orchard boot-argument comparison

The recovered Apple setup stores six 64-bit values:

```text
0x400000000  0x500000000  0x100000000
0x100000000  0x600000000  0x700000000
```

and the bootloader address `0xe1c0000000`. These are populated in an Apple
accelerator-owned descriptor before the META wait path.

Orchard's `pvr_fw_meta.c` does not consume an equivalent six-word array. It
builds a boot-configuration stream of `(register, value)` pairs, configures
the FW-data segment through `META_CR_MMCU_SEGMENT_N_*`, writes LDR records into
the allocated FW objects, and appends core-code and DMA arguments. Its code
allocation assumes the bootloader segment was configured before this path.

Therefore the Apple words cannot safely be translated by positional matching
to Orchard boot arguments. The remaining static task is to identify the
Apple descriptor's consumers and compare their resulting segment bases/limits
with Orchard's generated segment configuration. Until that correspondence is
recovered, slot 2 and the bootloader address remain a hard stop for firmware
execution.

No firmware bytes were copied or executed, and no device state was changed.
