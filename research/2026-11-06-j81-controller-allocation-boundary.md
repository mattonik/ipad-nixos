# J81 controller-allocation boundary

The AGX G4G vtable entry `+0x568` resolves to a small allocator that creates
a `0x16b0`-byte controller object and calls its initializer. The controller's
vtable `+0x70` method (`0xffffff800328486c`) only checks a shared capability,
zeros a `0xfe0`-byte linked-list region, and installs list links. The caller
then invokes that method with the AGX object and a timeout-derived argument.

This layer contains no GPU MMIO, firmware copy, DART setup, or firmware
execution. It is host-side bookkeeping between service registration and the
later firmware-service start/match path, so it is safe to model offline but
not a candidate for a hardware probe.
