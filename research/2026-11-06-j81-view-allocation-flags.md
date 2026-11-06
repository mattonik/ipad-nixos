# J81 four-view allocation flags

The 8.1 initializer allocates each of the first four firmware views as a
separate object. Every one uses the same allocator expression

```text
allocator_flags = provider_flags | 0x22
map_selector     = 0x80007
```

The requested sizes are independently rounded to the allocator's `0x2000`
granule, and each mapped object obtains its own address view before the packed
offsets are registered. The repeated pattern rules out the idea that the four
views are merely aliases of one Linux buffer with different offsets.

Other J81 helper paths use the same `0x80007` mapping selector with allocator
flag variants ending in `0x21` and `0x23`, so the low flag family is direction-
or buffer-role-related while the high selector field remains a separate
mapping-class choice. The exact private meaning of `0x22` and the physical
ownership path are still unresolved.

Evidence: `artifacts/live/private/gpu-offline/ios81-init-allocation.c` and
`ios81-memory-helpers.c`. No firmware or device state was touched.
