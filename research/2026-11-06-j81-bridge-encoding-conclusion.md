# J81 bridge value encoding: offline conclusion

The recovered iPadOS 15 PMGR code narrows the meaning of the first bridge
value. Its table writer computes the selected bridge window and offset, then
stores the table's 32-bit value verbatim; the PMGR layer does not add or strip
`0x80010000`. The generic bridge callback also dispatches table entries by
index and returns only a status code.

Therefore the live transition from a table value of `0x80010004` to a stable
readback of `0x00000004` is a property of the bridge/GFX register itself (for
example write-only/tagged control bits being read as zero), not a PMGR-side
value conversion. The PMGR device-state reader's separate `& 0xf` masking
cannot be used to explain this MMIO readback.

This removes one ambiguity but does not identify the high bits' hardware
meaning. Keep the remaining bridge table and GPC writes blocked until an
A8X-specific register contract or a separately reviewed observation exists.
