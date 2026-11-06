# META bootloader slot comparison

The local Orchard G5P transport patch makes the special handling of the
bootloader segment explicit.  Its boot configuration uses four segment bases:

```text
0x10000000  0x20000000  0x40000000  0x60001000
```

but segment 2 is emitted as only one register/value pair (`reg + 12`) with a
`0x100` high-VA marker; it does not receive the normal four-register base,
size, and address tuple.  The other segments receive the complete tuple.

This is consistent with the J81 audit: Apple slot 2 is a distinct
`META_BOOTLOADER` region rather than an ordinary `FW_DATA` or `FW_CODE`
allocation.  The arithmetic candidate at `0x40000000` is therefore useful as
a location hypothesis, but cannot be treated as a normal Linux allocation
until the preconfigured bootloader segment and the Apple descriptor's
`0xe1c0000000` field are matched.

The G5P implementation is not evidence that the same register numbers or
firmware apply to G4G.  The reusable result is the contract shape: preserve a
separate bootloader-slot state and reject execution if it is silently folded
into the generic FW-data path.

Evidence: `orchard-g5p-transport.patch` `g5p_make_boot_config()` and
`g5p_image_offset()`, plus `research/2026-11-06-j81-g4g-layout-audit.md`.
No firmware or hardware access was performed.
