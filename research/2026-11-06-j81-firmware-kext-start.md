# J81 `AGXFirmwareKextG4G` start boundary

The firmware kext vtable at `0xffffff8002e50080` contains the concrete
`start` override at slot `+0x2a8`:

```text
vtable[0x2a8] = 0xffffff8002e3919c
```

The routine is short and unambiguous:

1. call the superclass start through the parent vtable stored at
   `0xffffff8002e50040 + 0x2b8`, which resolves exactly to
   `IOService::start` at `0xffffff80023aee88`;
2. call the firmware object's `IOService::registerService(0)` at vtable
   offset `+0x298`;
3. return the superclass-start result.

This rules out the G4G kext's own `start` method as a firmware-launch routine.
It contains no GPU MMIO access, power transition, DART setup, descriptor
submission, or firmware execution.  The superclass call is generic
`IOService::start`, not evidence of an A8X firmware ABI.  The remaining
GPU-specific unknowns are the firmware image identity, address translation,
and later command/interrupt ownership.

The host contract therefore changes its unresolved item from “find the G4G
start/match implementation” to a concrete `firmware-kext-start-review`
boundary; execution remains disabled.
