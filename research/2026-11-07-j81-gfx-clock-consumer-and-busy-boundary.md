# J81 GFX clock consumer and busy callback boundary

Offline follow-up to `2026-11-07-j81-gfx-clock-reference-startup-audit.md`.
No device access or firmware execution was performed.

## Gate-ID consumer inventory

The preserved J81 device tree (`artifacts/live/private/gpu-offline/ios81-dt.json`)
was walked recursively for every `clock-gates` property. Of the nodes in that
capture, only `/arm-io/sgx` declares clock ID 124 (`clock-gates = [124]`);
its `power-gates` entry is also 124. The neighboring display, DART, codec,
storage, and PCIe nodes use other IDs. This makes an earlier static device-tree
consumer of clock ID 124 unlikely. It does not exclude a driver dynamically
calling an `AppleARMIODevice` provider with ID 124 or the runtime ordering of
service probes.

The matching G4G probe body is recovered in
`artifacts/live/private/gpu-offline/gpc-link.c` at
`FUN_ffffff80032935a0`: after its superclass probe and G4G property hook
succeed, it calls provider `+0x560` to enable the clock, then `+0x568` to
enable power, before GPC mapping/writes. Its later cleanup disables power and
then clock only when the power callback's local output is nonzero. Therefore
G4G's clock request is real and early in its probe, but the static call order
does not prove it is the first runtime client.

## What a clock edge actually does

In `t7000-clock.c`, the PMGR clock callback increments on enable. Disable
decrements only when the count is nonzero, so a disable at zero does not
underflow. The desired state is nonzero-count for ordinary records; the
controller compares it with its tracked active bitmap and schedules the
transition only on a mismatch. For GFX, that edge enters the action list:
PMGR state-index 100 is requested at 15 and polled by the state helper, then
selector 9 and selector 10 tables are stored, then the SoC-busy helper is
called. No edge means no replay of these actions. Startup seeds the tracked
state from PMGR actual state, so count-zero alone does not imply an enable edge.

`gfx-clock-special.c` shows the busy helper's split effects. It always changes
the controller's software busy count and logs an unbalanced disable at zero.
The display/MCC path requires all of: the controller feature value at `+0x980`
nonzero, the byte at `+0x98c` nonzero, a busy-count boundary transition
(0→1 or 1→0), and a resolved callback object at `+0x990`. It then dispatches
the callback and only follows the successful-return branch for additional
display/power bookkeeping. Thus the busy reference accounting is part of the
clock edge, but display/MCC work is conditional and cannot be asserted from the
hardware replay logs.

## Test4 boundary and next uncertainty

Test4's direct replay covered the selector writes and GPC setup, not the
provider clock callback, reference count, tracked-state comparison, PMGR
workloop transition, or busy count. The startup audit therefore identifies a
valid software/control-flow gap even where the visible selector-table writes
match. There is no evidence here that the gap caused the RGX identity read
stall, nor that a Linux replay of Apple's callback path is safe.

The remaining material uncertainty is runtime state at G4G probe: whether any
dynamic client requested ID 124 first and whether PMGR's tracked GFX bit was
active. Resolving that requires runtime observation or stronger static tracing
through all dynamic clock-provider calls plus their probe order; the ADT
inventory alone does not close it.
