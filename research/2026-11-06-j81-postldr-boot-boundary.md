# J81 post-LDR boot boundary

The next iOS 8.1 AGX routines clarify the sequencing after the LDR copy:

1. `0xffffff800329e5f4` calls the preparation routine once and caches success.
2. `0xffffff800329e63c` parses the packed layout, allocates/maps the preparation
   object with selector `0x70007`, registers four address views through vtable
   `+0x210`, and invokes the CPU copy/verify routine.
3. `0xffffff800329e894` waits for the firmware-alive callback. On success it
   calls the accelerator power/clock hooks at vtable `+0x1e0` and `+0x6d8`,
   logs `GPU firmware booted successfully`, and marks the firmware alive.

The wait routine itself only polls the host callback and the existing META
status path; it does not discover or program a DART aperture. The neighboring
startup routines write META control/status offsets such as `0xa08`, `0xa10`,
`0xa18`, `0x100`, `0xbf8`, and `0x1340`, then wait for META idle/alive bits.
Those writes are a later boot/handshake boundary, not evidence that the four
LDR views are GPU IOVAs.

This narrows the next static target to the accelerator vtable hooks reached by
`+0x1e0`, `+0x6d8`, and the first post-alive command path. No firmware was
executed and no hardware state changed.
