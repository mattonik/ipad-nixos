# J81 G4G firmware-alive contract (offline, 2026-11-06)

The iOS 8.1 G4G path has a concrete post-load wait sequence in the recovered
`AGXAcceleratorG4G` code:

* the provider event callback accepts event type `0` and sets an alive byte at
  object offset `0x5ca`;
* it records the event payload at `0x5d0` and signals the event source through
  the provider's `+0x100` method;
* the boot wait routine observes that byte, then waits for a separate success
  byte at `0x5cb`;
* it performs up to ten one-second event waits through the provider object at
  `+0xaf8`, `+0x108`, and reports a META timeout if the success state never
  arrives;
* after success it calls the provider completion path and marks the booted
  state. A later failure path reports either “agxbootd did not boot firmware”
  or “Firmware not alive”.

This is more specific than the earlier generic “alive handshake unresolved”
label, but it is not a recipe for Linux: the provider event source, event
payload, and success-byte producer are Apple object/interrupt plumbing.

Orchard's Linux META driver uses a different contract. It allocates the FWIF
connection/sysinit objects, starts META, and polls
`fwif_sysinit->firmware_started` until `FW_BOOT_TIMEOUT_USEC`; later health is
checked through FWIF/KCCB commands. No Apple event-source equivalent is
present in the generic Linux path.

Conclusion: stages 1–2 now have a bounded static target—an Apple event-backed
alive notification must be adapted to Linux's shared FWIF state or explicitly
replaced by a J81-specific completion path. It is not safe to claim the
generic Linux boot wait is compatible merely because both paths expose an
“alive” result.
