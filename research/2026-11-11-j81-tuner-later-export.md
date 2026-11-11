# J81 tuner: a later boot-log export candidate

Offline work on the existing 19H394 kernel and the private November 11 tuner
boot archive. No new hardware access.

The captured boot logs `P1=... G1=... I=...` and the zero `U` marker at
14:42:43.471 local time. It later logs `GPU firmware booted successfully
(AGXFirmwareKextG4G)` at 14:42:43.585, approximately 114 ms later in the
decoded log. The lines have different thread identifiers; timestamps and
thread IDs alone do not prove a particular tuner or display event occurred
between them. The success message is nevertheless an observed later logging
event on this instrumented boot, not a hypothetical location.

The 19H394 kernel contains the success format string at
`0xfffffff0057cbf2a`. In the existing AGX disassembly, code at
`0xfffffff0066903d8`–`...03e4` prepares that string and its stack arguments,
then calls the same logging target used by the existing probe,
`0xfffffff0066b0ff4`. The six 32-bit instruction words starting at
`...03d8` are `a90003f5 f0ff89c0 913ca800 94008304 52800028 392cde68`;
that exact 24-byte pattern occurs once in the full 19H394 kernel file. The
existing [firmware lifecycle trace](2026-11-09-j81-ios15-firmware-lifecycle-order.md)
places this code in a later controller path. A static unique match does not
prove correct relocation, branch reachability, runtime context, or safe
instrumentation.

## What a second snapshot could answer

The current tuner hook stores `entry-seen` and `exit-seen` independently of
its GFX-window flag. A separately reviewed hook at the later success log
could snapshot those global controls a second time while preserving the
original logger call, arguments, registers, flags, stack and output. If an
early `U` says both controls are zero and a later snapshot says either is
nonzero, that would demonstrate the corresponding tuner hook executed by
that later point. It would not establish a particular device-set cause,
completion of asynchronous work, or that the tuner ran before GPU identity.
Zero at both points remains inconclusive; patch install, runtime binding,
publication races and the handler's execution still need positive evidence.

This later point is only about a tenth of a second after identity in the
saved boot. It cannot report a brightness change performed by the user after
the Home screen appears. No user-controlled trigger or safe post-interaction
export point has been established. This candidate therefore improves the
startup observation window, but is not a complete later-interaction positive
control. Do not call the logger from the tuner/command-gate hook itself.

Any implementation needs exact-kernel and unique-signature guards, a
safe relocation strategy for the original `bl` and stack-passed arguments,
host tests for preservation and both output snapshots, and recovery planning.
The old hook only drains at identity; no later-export probe has been built or
run. Full kernel images and the device log are private.
