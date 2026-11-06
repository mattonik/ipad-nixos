# J81 Apple LDR copy and verification proof

The recovered Apple routine `0xffffff800329fbe8` closes another part of the
loader model. For each `LoadMem` record it computes the packed destination from
the segment minimum and packed offset, copies the bytes, then compares every
copied byte against the source and fails on the first mismatch. `ZeroMem`
records use the same segment arithmetic unless they fall under the Apple
core-memory guard. `StartThreads` records are parsed into a separate thread
structure, and config records update the host boot state rather than being
treated as ordinary loads.

This confirms that the existing packed-offset arithmetic models Apple’s copy
destination correctly, but it also confirms that allocation ownership and
cache/address views are prerequisites: the copy verifier only proves bytes in
the selected host view, not GPU visibility. Orchard’s generic loader still
cannot be substituted until the Apple bootloader segment and allocation views
are mapped explicitly.

No firmware bytes were copied by our tools and no device state was changed.
