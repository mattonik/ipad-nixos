# J81 relative view equivalence

The Apple call site passes `mapped_preparation_base + packed_offset[index]` to
vtable `+0x210`. The four offsets are the same contiguous packed layout already
recovered from the LDR image. Orchard's synthetic plan uses
`ROGUE_FW_HEAP_BASE + packed_offset[index]`.

Therefore the two systems agree on the **relative** four-view layout:

```text
base + {0x00000, 0x0f000, 0x13000, 0x14000}
```

The unresolved part is only the absolute base and ownership/cache attributes:
Apple obtains its base from a private allocator view, while Orchard obtains a
FW heap address from its own object allocator. This is enough to reuse the
offset calculator, but not enough to substitute Orchard addresses on hardware.
