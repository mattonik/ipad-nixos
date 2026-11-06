# J81 physical/view address pair

The initializer keeps two addresses for every mapped allocation:

- the mapped view's `+0x80` result, used for host-side structure access and
  firmware-view registration;
- the backing object's nested `+0x140` result, retained separately before the
  view is consumed.

The four main firmware views all use this pair with allocator flags ending in
`0x22`. Later 0x400-byte scratch objects use the same `0x80007` map selector
with flags ending in `0x21` and `0x23`, giving distinct direction/role variants
while preserving the same physical-versus-view split.

This is stronger than a generic “DMA mapping” description: the Apple host keeps
both a backing/physical identity and a mapped view identity, and passes only
the view-derived base to the four-view registration callback. A Linux adapter
must preserve that ownership relationship; a single `dma_alloc_coherent()`
pointer is not yet proven equivalent.

Evidence: `artifacts/live/private/gpu-offline/ios81-init-allocation.c`, around
the four `0x22` allocations and the later `0x21`/`0x23` scratch allocations.
No firmware or hardware access was performed.
