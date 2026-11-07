# J81 provider-view static limit

The Apple allocator helpers show that each resource first becomes an
`IOMemoryDescriptor` and an `IOMemoryMap` (`createMappingInTask(..., 0x101,
...)`). The retained map object's `+0x80` resolves to
`IOMemoryMap::getVirtualAddress`; the accelerator's private `+0x90` selector
(`0x90007`) is a separate view/policy operation. Correction: the four values
passed through accelerator vtable `+0x210` in `0xffffff800329e63c` are
derived from **one preparation object's map**, plus four packed offsets.
Other allocations in the initializer have their own objects and maps; they
must not be conflated with these four registrations. The base is a runtime
virtual address, not a constant encoded in the firmware image or device tree.

This is the current offline ceiling: static analysis recovers the packed
offsets and the object/view call sequence, but cannot recover the runtime base
addresses without executing Apple's allocator. Orchard's heap allocator is a
different ownership and mapping system, so substituting its addresses would
be a new implementation assumption rather than a recovered fact.

The safe artifact boundary is now explicit: generate a four-view registration
plan with unresolved bases, reject execution when any base is absent, and use
the plan only in a synthetic test until a separately approved runtime
experiment can observe the address-view behavior.

Evidence: `artifacts/live/private/gpu-offline/firmware-prepare.c`: the map is
stored once at `param_1[0xae]`; the loop calls that same map's `+0x80` four
times and adds the indexed `param+0x524` offsets. This establishes the
common base, not the target address space or the behavior of `+0x210`.
