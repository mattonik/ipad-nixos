# Interpreting the first J81 bridge peek

The live read of `0x201f00018` returned `0x00000004`. The static J81 table
would write `0x80010004` to that same address as the first entry of selector 9
and selector 10.

This establishes one useful but limited fact: the observed low word matches
the low 16 bits of the Apple table value, while the high control bits
(`0x80010000`) are not present in the readback. That is consistent with a
command/configuration register whose write-only or tagged bits are masked on
readback. It is not proof that the low bits are a status field, nor proof that
the table write is safe.

The offline iOS 15 PMGR decompilation shows the bridge service dispatching
opaque table entries through a generic register-write callback. It does not
name the `0x80010000` bits or provide an A8X-specific readback contract. The
Orchard A9 sources in this checkout likewise contain no matching A8X bridge
definition.

## Consequence

Do not replay `0x80010004`, the remaining 66-entry tables, or the GPC init
sequence based on this observation alone. The next productive step is more
static work: identify the PMGR bridge callback's register encoding and compare
its A8X/A9 table consumers. If that remains opaque, the next hardware test
should be explicitly reviewed as a write experiment with a fresh boot and a
new recovery plan—not appended to this read-only session.
