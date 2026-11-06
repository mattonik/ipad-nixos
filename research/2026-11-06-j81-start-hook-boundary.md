# J81 derived start-hook boundary

The final call in `0xffffff800329d7d8` is an indirect call through the
object's vtable at offset `+0xc0` (`[x19] + 0xc0`). The apparent base vtable
at `0xffffff80032b2d70` has `0xffffff800238dc04` in that slot. The kernelcache
symbol table resolves that address to `___cxa_pure_virtual`, not to a GPU
operation.

This means the routine is a descriptor-builder/base-class method. Its fixed
class values, optional controller value, bootloader address, and translated
views are the last statically visible metadata. A concrete J81 subclass must
replace the `+0xc0` slot with the actual start hook; the base image does not
reveal that implementation through this call site. The hook is therefore an
unresolved execution boundary, not evidence that firmware has been started.

The host simulator records this as `subclass-start-hook-review` and remains
execution-disabled. Recovering the body requires locating the concrete vtable
instance/factory or a later image with the derived class, then proving its
side effects before any hardware attempt.
