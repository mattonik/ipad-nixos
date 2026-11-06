# J81 legacy mapping-bit context

The iOS 8.1 allocation helper uses the same `0x80007` mapping option with allocator flags ending in `0x22`, `0x21`, and `0x23` (physical descriptors with out, in, and bidirectional directions). Therefore the high `0x80000` bit is independent of transfer direction; it belongs to the common mapping policy, not to the read/write classification.

This rules out interpreting `0x80000` as a hidden direction bit. The recovered call sites still do not expose whether it selects a cache, address-space, or legacy mapper behavior, so the Linux equivalent remains intentionally unspecified.
