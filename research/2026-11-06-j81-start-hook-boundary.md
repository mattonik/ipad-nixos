# J81 final virtual-hook boundary

The final call in `0xffffff800329d7d8` is an indirect call through the
object's vtable at offset `+0xc0` (`[x19] + 0xc0`). The constructors in this
class store `0xffffff80032b2d80` (the data table at `0xffffff80032b2d70`
plus the Itanium header) as the object vptr; its `+0xc0` entry is
`0xffffff800238dc04`. The kernelcache symbol table resolves that address to
`___cxa_pure_virtual`, not to a GPU operation.

The separate `AGXFirmwareKextG4G` image extracted from the same kernelcache
has a concrete vtable at `0xffffff8002e50080`; its `+0xc0` entry is
`IORegistryEntry::setProperty(const char *, OSObject *)`. This makes a final
property/publication hook plausible, but the runtime vptr used by the J81
descriptor object is not proven at this call site. The call is therefore not
evidence that firmware has been started.

The host simulator records this as `final-property-hook-review` and remains
execution-disabled. Recovering the actual firmware-start body requires
locating the concrete firmware-controller method after this publication step,
then proving its side effects before any hardware attempt.
