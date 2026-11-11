# J81 bridge value encoding: offline conclusion

The recovered iPadOS 15 PMGR code narrows the meaning of the first bridge
value. Its table writer computes the selected bridge window and offset, then
stores the table's 32-bit value verbatim; the PMGR layer does not add or strip
`0x80010000`. The generic bridge callback also dispatches table entries by
index and returns only a status code.

The table value `0x80010004` and a fresh-boot no-write readback of `0x4`
come from different boots and phases; they do not demonstrate a live
transition or establish the high bits' behavior. The PMGR device-state
reader's separate `& 0xf` masking cannot explain the direct MMIO readback.
See the later [readback audit](2026-11-11-j81-bridge-readback-candidate.md).

This removes one ambiguity but does not identify the high bits' hardware
meaning. Keep the remaining bridge table and GPC writes blocked until an
A8X-specific register contract or a separately reviewed observation exists.
