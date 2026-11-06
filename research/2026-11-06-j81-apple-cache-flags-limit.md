# J81 Apple cache-flag limit

The iOS 8.1 and iPadOS 15 decompilations show the same memory-object map
option `0x80007` and allocator flag families `base | 0x21`, `base | 0x22`, and
`base | 0x23`. These values select Apple IOKit memory-object behavior, but the
private vtables for the allocator and map objects are not present as named
source, so the bit meanings cannot be recovered from the call sites alone.

The evidence is enough to say that Apple uses distinct allocation classes and
mapping options; it is not enough to label them cached or uncached. The view
comparison therefore correctly keeps Apple cache mode unknown and rejects
Orchard FW-object substitution.

Next static target: resolve the allocator/map vtable implementations or their
public IOKit option definitions. Until then, no cache-compatible hardware
plan can be claimed.
