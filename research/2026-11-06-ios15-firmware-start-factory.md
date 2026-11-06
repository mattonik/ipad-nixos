# iPadOS 15 firmware-start factory cross-check

The preserved iPadOS 15 G4G pre-probe decompilation gives a useful analogue
for the unresolved J81 subclass hook. After provider setup and the common
startup callback, `0xfffffff00666d6e4` calls accelerator vtable `+0x848` to
obtain a firmware object. It then calls the accelerator's `+0x818` initializer
and the returned firmware object's `+0x78` setup method before entering the
rest of the firmware-controller initialization. A later accelerator `+0x2c0`
call continues the controller setup.

This is not a portable boot recipe: the iPadOS 15 object layout, vtable
offsets, and firmware ABI differ from J81. It does, however, narrow the J81
search target. The concrete implementation behind the J81 `+0xc0` handoff is
likely a factory/initializer chain analogous to this sequence, rather than a
direct render or doorbell write. The next offline search is for the J81
factory that creates the firmware object and for its first non-pure virtual
method; no hardware execution is justified by this analogy.
