# J81 G4G firmware-alive contract (offline, 2026-11-06)

The iOS 8.1 G4G path has a concrete post-load wait sequence in the recovered
`AGXAcceleratorG4G` code:

* the provider event callback accepts event type `0` and sets an alive byte at
  object offset `0x5ca`;
* it records the event payload at `0x5d0` and signals the event source through
  the provider's `+0x100` method;
* the boot wait routine observes that byte, then checks a separate success
  byte at `0x5cb`;
* it performs up to ten one-second event waits through the provider object at
  `+0xaf8`, `+0x108`, and reports a META timeout if the success state never
  arrives;
* when the alive byte is set and the success byte is clear, the wait routine
  calls identity methods `+0x1e0` and `+0x6d8` for a log message, then sets
  the success byte itself. A later failure path reports either “agxbootd did not boot firmware”
  or “Firmware not alive”.

This is more specific than the earlier generic “alive handshake unresolved”
label, but it is not a recipe for Linux: the provider event source, event
payload, and success-byte producer are Apple object/interrupt plumbing.

The same 8.1 host setup writes a six-entry boot descriptor containing
`0x400000000`, `0x500000000`, `0x100000000`, `0x100000000`, `0x600000000`,
and `0x700000000`, followed by the `0xe1c0000000` bootloader address. These
values are concrete Apple-side boot arguments, but their field meanings and
relationship to Linux's generated META boot-argument list are not established.

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

## Adapter and producer limits

The host model represents only the observed Apple-side steps as
`APPLE_WAITING` → `APPLE_EVENT_0` → `APPLE_HOST_ACCEPTED`: it injects event 0,
then models the wait routine promoting the success byte. It does not model or
claim a META-start producer, callback registration, or interrupt delivery.
The wait/wake object at provider `+0xaf8` is now resolved from the local iOS 8.1
kernelcache as an `IOCommandGate`: object vtable offsets `+0x100/+0x108` are
`commandWakeup` and timed `commandSleep`. This is host synchronization, not the
GPU interrupt source. Callback registration, event producer, and interrupt
dispatch remain unknown, so this is not a proven end-to-end J81 sequence. See
[`2026-11-07-j81-g4g-event-dispatch.md`](2026-11-07-j81-g4g-event-dispatch.md).
Do not require the generic Linux
`firmware_started` flag or assume Apple firmware implements IMG FWIF. Orchard's
[A10 integration](https://github.com/OrchardLinux/orchard/commit/b5e37693bb1246ce566406a205ae0ca834cdc18e9)
branches to `pvr_device_gpu_init_apple()` before `pvr_request_firmware()` and
uses `pvr_apple_fw_init()` instead of `pvr_fw_init()`. It boots a different,
flat A10 image through RTKit; this is evidence of an alternative integration,
not proof that the same transport applies to J81.

The recovered 8.1 routine `0xffffff800329e894` is itself a writer of `0x5cb`:
after `0x5ca` is set, it calls the two identity methods above and sets the
byte without another explicit readiness predicate in that routine. As recorded
in [the vtable sequence](2026-11-06-j81-firmware-vtable-sequence.md) and [post-LDR
boundary](2026-11-06-j81-postldr-boot-boundary.md), the symbol table identifies
`+0x1e0` as `IORegistryEntry::getName`; `+0x6d8` resolves to
`0xffffff800328fa28`, whose decompilation returns the class-name string. Those
calls do not establish another hardware readiness condition.
The callback `0xffffff800329f6cc` is the observed event-0 latch writer, but a
read-only Ghidra cross-reference search finds only the data reference
`0xffffff80032b3230`; it does not identify the producer or interrupt source.
Both findings come from the private `ios81-postldr.c` decompilation and must
be checked against the original instructions before a hardware implementation.
Resolving callback dispatch and its event producer is the next offline target. No firmware was executed or hardware accessed.
