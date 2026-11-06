# J81 Apple boot-descriptor owner

The iOS 8.1 initializer identifies the owner of the six-word descriptor more
precisely than the raw values suggested. It creates a second aligned shared
allocation whose mapped base is saved, then places the descriptor at
`mapped_base + uVar7`, where `uVar7` is the aligned size of that allocation.
The thread-use routine writes the six words at descriptor offsets `0..0x28`,
then stores the bootloader address at offset `0x210` and another provider
value at `0x208`.

Thus the values are fields in an Apple host-side control structure, not a
standalone GPU allocation table. Their consumers are downstream Apple
provider methods. This explains why positional comparison with Orchard's
boot-configuration pairs failed and gives the next reverse-engineering target:
resolve the provider call that consumes this structure.

No firmware or device state was touched.
