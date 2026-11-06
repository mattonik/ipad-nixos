# J81 provider-view static limit

The Apple allocator helpers show that each resource first becomes an
`IOMemoryDescriptor` and an `IOMemoryMap` (`createMappingInTask(..., 0x101,
...)`), then the accelerator's private `+0x90` view selector (`0x90007`)
returns the mapped address view. The four values passed through accelerator
vtable `+0x210` are therefore runtime virtual addresses derived from separate
allocation objects, not constants encoded in the firmware image or device
tree.

This is the current offline ceiling: static analysis recovers the packed
offsets and the object/view call sequence, but cannot recover the runtime base
addresses without executing Apple's allocator. Orchard's heap allocator is a
different ownership and mapping system, so substituting its addresses would
be a new implementation assumption rather than a recovered fact.

The safe artifact boundary is now explicit: generate a four-view registration
plan with unresolved bases, reject execution when any base is absent, and use
the plan only in a synthetic test until a separately approved runtime
experiment can observe the address-view behavior.
