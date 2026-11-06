# J81 firmware vtable sequence

The iOS 8.1 firmware-object vtable around `0xffffff80032b30a8` confirms the
post-LDR method order:

The contiguous entries point to:

- `0xffffff800329e5f4` — cached firmware preparation
- `0xffffff800329e894` — wait for firmware-alive callback
- `0xffffff800329ea10` — META-slave readiness/reset polling
- `0xffffff800329eb28` — restart/handshake sequence
- `0xffffff800329eff0` — firmware stop/cleanup
- `0xffffff800329f284`, `...f3c8`, `...f588` — alive/error callbacks

The preserved kernelcache symbol table resolves the apparent `+0x1e0` hook in
the alive path to `IORegistryEntry::getName`; the following `+0x6d8` hook is a
class-name getter. Neither is a power, clock, DART, or command operation.
The first routines after the alive wait operate on the META status/control
window and invoke firmware-object callbacks. This is still firmware control
plane work, not a GPU render submission path.

The firmware object's `+0x1c0` call in `0xffffff800329eb28` is also resolved by
the kernelcache symbol table: it is `IOService::disableInterrupt(int)`, called
after the META preparation steps. It is interrupt hygiene, not command or DART
setup. The next meaningful static target is the first method that writes a
command/ring address rather than META handshake state.
