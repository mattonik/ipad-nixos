# J81 IOKit memory-flag interpretation

The local Darwin IOKit headers resolve the low allocator bits used by the
Apple G4G initializer:

| value | header interpretation |
|---:|---|
| `0x21` | physical memory descriptor + direction-in |
| `0x22` | physical memory descriptor + direction-out |
| `0x23` | physical memory descriptor + in/out |
| `0x80007` | direction in/out plus a legacy high mapping option; exact high-bit meaning remains version-specific |

This resolves the allocation **type and direction**: the G4G objects are
physical I/O memory descriptors, not ordinary pageable virtual buffers. It
does not resolve cache policy; the public headers expose cache mode as a
separate mapping field, and the recovered call sites do not set a named cache
mode.

The adapter should therefore require `physical_io` ownership and keep cache
mode unknown, rather than labeling Apple views `uncached`.
