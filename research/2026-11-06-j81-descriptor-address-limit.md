# J81 descriptor-address limit

The provider map address getter (`0xffffff800326d018`) has one unresolved
call: the retained descriptor's virtual `+0xa8` method when map state bit 6 is
set.  Static tracing establishes the surrounding facts:

- the map is allocated by provider `+0x6c0` and initialized with selector
  metadata by `0xffffff8003281ab8`;
- the map stores a provider/descriptor relationship and has no direct GPU
  register access;
- the getter either returns `map+0x90` or delegates to the retained
  descriptor's `+0xa8`;
- the descriptor object is supplied through generic provider construction, so
  its concrete vtable is not recoverable from the caller alone.

The extracted IOAcceleratorFamily2 image contains several `IOAccelSysMemory`
constructors, but their vtable provenance does not match the map object's
retained descriptor unambiguously.  Treating that class as the target would be
an inference, not a recovered fact.  The safe conclusion is therefore that
the final address type (CPU virtual, physical, or device/DART) remains
unresolved and must not be guessed in Linux.
