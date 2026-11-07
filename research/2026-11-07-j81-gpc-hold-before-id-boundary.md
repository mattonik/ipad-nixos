# J81 GPC hold is not a demonstrated pre-ID prerequisite

Offline trace after test4. No hardware was accessed.

## Exact first-ID dispatch on the G4G object

The early path is an `AGXAcceleratorG4G_A0` object. Its constructor installs
vptr `0xffffff80032aefa0` (the class/personality mapping is in
`2026-11-04-j81-gpu-offline-trace.md`). This pins the two relevant virtual
calls to concrete entries in that vtable:

* `vptr + 0x800` at `0xffffff80032af7a0` ->
  `0xffffff80032933cc` (`ident.c`).
* `vptr + 0x810` at `0xffffff80032af7b0` ->
  `0xffffff800328de68` (`ios81-agx-disasm.txt`).

`32933cc` dispatches `+0x810`; `328de68` reads the mapped RGX window at
`+0x20`, then `+0x18`. The blocked `0x201000020` transaction in test4 is
therefore the first identity read in this exact early path. It is not reached
through an `AGXMetaFirmware` method.

Before the GPC writes, `FUN_ffffff80032935a0` first maps the RGX resource,
then calls accelerator slot `+0x790` on the proven `32aefa0` vptr. That slot
is `0xffffff80032861c4` (`preprobe.c`): it reads provider properties
`no-gpc` and `model-slow` and sets accelerator flags `+0xbac` and `+0xbae`.
For J81, `no-gpc` is absent, so the GPC poll flag remains enabled. This hook
does not access MMIO. It then calls the provider object's `+0x560(1,0)` and
`+0x568(1,&local,0)`. The matching AGX personality
requires `AppleARMIODevice`; the resolved J81 implementation is the generic
provider wrapper forwarding gate ID `0x7c` through `AppleT7001IO` to the
T7000 PMGR callbacks (full chain in
`2026-11-07-j81-gpc-provider-object-binding.md`). It then writes GPC
`+0x10000=0xffff0000`, `+0=0x40000000`, `+0x1000=0x11`, polls state bit 4
clear when enabled, delays 10 us, and calls the accelerator's `+0x800`
identity method. Only after that method returns does this path write
`GPC+0x1000=0x10` (state zero), poll bit 4 clear, and possibly call provider
power-off then clock-off if the power-history out value requested unwind.

## The hold method belongs to a different object and path

`FUN_ffffff800329eb28` is stored at `0xffffff80032b30f8`, offset `+0x50`
in a separate firmware-object vtable table based at `0xffffff80032b30a8`.
Its receiver/layout and its GPC mapping via `param1[2]` identify a firmware
object path, unlike the accelerator's `+0x800` identity dispatch above.
The runtime subclass/vptr selection for this firmware object is not resolved,
so this table is not claimed as the live firmware object's proven vptr. Its
body requests hold by writing `0x20` to GPC `+0x20000`, polls that
hold bit, polls GPC state bit 4 clear, and then writes base control
`0x40000000`. This is a hold/state-zero/control sequence for the firmware
control path. The available static call evidence does not place this method
before the early accelerator identity call; the early path's actual `+0x800`
vptr entry is already resolved to `32933cc`.

Do not merge these sequences based on shared GPC addresses. The early G4G
probe enters RGX identity before its state-zero cleanup. The firmware-object
method's hold followed by state-zero is a distinct operation with different
receiver/vptr and mapped object. The static evidence cannot rule out every
external platform or boot-firmware prerequisite, but does rule out treating
`329eb28` as the target of the direct pre-ID accelerator `+0x800` dispatch.

## Test4 comparison and decision

The test4 captures show the Linux probe reached PMGR `0x3ff`, GPC state 1,
GPC control `0x40000000`, and the first-read checkpoint at
`0x201000020`; it never recorded an after-read checkpoint and USB networking
failed. The 66 table writes and post-GPC bridge reads also completed. Linux
did not run Apple's provider-object callbacks or its later GPC state-zero
cleanup, but those cleanup calls occur after the identity method and cannot
be the missing cause of the first read. Linux also did not run the firmware
object's hold method; no evidence shows that method is on the pre-ID path.

There is no source-supported bounded live test to propose. Replaying the
firmware hold sequence would change an undocumented GPC control state without
evidence it gates the early ID port; retrying the ID read already hangs. A
useful next action is static only: retain the exact object/vptr distinction
and inspect any newly available 12B410 boot/provider call path for a pre-ID
call to the firmware method or another setup routine. Until such a call is
found, classify the omitted reset/hold behavior as unproven, not as the fix.

## Exact pre-ID call chain and Linux transition delta

The `+0x800` matcher has one non-MMIO dispatch before the actual ID read.
At the proven accelerator vptr, `+0x808` (`0xffffff80032af7a8`) resolves to
`0xffffff800328de5c`, which simply returns the static address
`0xffffff80032b62b0` (the model/identity table). `32933cc` returns early if
that pointer is null; otherwise it calls `+0x810` (`328de68`). That method
loads the RGX mapping pointer from accelerator `this+0xaf0`, then performs
32-bit loads at mapping `+0x20` followed by `+0x18`, combines the identity
fields, and returns. The `+0x808` call is not a hidden register access or a
hold operation. No extra virtual callback appears between these two methods.

The Apple G4G sequence, as encoded at `32935a0`, is therefore: map RGX;
accelerator `+0x790` property hook; provider `+0x560(1,0)`; provider
`+0x568(1,&local,0)`; map Fender/GPC; write
`GPC+0x10000=0xffff0000`; write `GPC+0=0x40000000`; write
`GPC+0x1000=0x11`; optionally busy-poll bit 4 clear; call `IODelay(10)`;
log/startup bookkeeping; accelerator `+0x800`; `+0x808` table pointer;
`+0x810` reads RGX `+0x20` then `+0x18`. After matcher return, Apple writes
`GPC+0x1000=0x10` and optionally polls bit 4 clear, then conditionally
releases provider power before provider clock according to the callback's
out value. Its GPC poll has no visible timeout in this method. The initial
GPC state is not explicitly read before those writes in this path.

Linux `boot/gpu-gpc-init.c` does a different, tightly checkpointed operation:
it first requires `GPC+0x1000 == 0`, writes the same three values in the
same order, then reads `GPC+0x1000` up to 64 times and accepts only state 1.
It does not invoke provider `+0x560/+0x568`, does not acquire Apple's
per-device clock/power wrappers, does not execute `IODelay(10)`, does not
call identity, does not write state zero, and does not release provider
state. Its operation wrapper logs the intended value after a write; that
checkpoint is not a write readback. It also has a bounded host ACK at each
read/write, unlike Apple's in-kernel tight poll. The PMGR genpd reference and
selector-table application are separate Linux stages, not actions performed
by `gpu-gpc-init.c`.

The test4 core-read capture is consistent with this distinction: its own
preconditions read PMGR `0x3ff`, GPC state `1`, and control `0x40000000`, then
the `before-gpu-revision` marker at `0x201000020` receives no completion.
This shows the Linux request/control transition and state read succeeded;
it does not show Apple's clock/power callbacks or ID matcher reached a
readable state. The Apple 10-us delay is only a static sequence detail, and
there is no evidence it explains the hang or warrants a repeat read. No
additional MMIO is supported by this comparison.

### Delay timing evidence

The GPC-init host-stage timestamps in `gpc-init-20261107-test4.log` place
`after-poll-00` at `1794047696445422000 ns` and watchdog disarm at
`1794047696446779000 ns` (1.357 ms later). The subsequent post-GPC bridge
capture file has mtime `1794047702` seconds and the core-revision capture
file has mtime `1794047710` seconds, 13.55 seconds after the poll ACK by
timestamp arithmetic. These file times, plus the documented
phase order, place the core-read capture several seconds after the GPC-init
phase; they are not timestamps for the core-read `before` marker. The
core-revision log contains no `host-stage time_ns` records, so an exact
poll-to-core-read interval cannot be recovered. The available evidence does
not establish the numeric interval as greater than 10 microseconds, though
the separate host-mediated phase timings make a sub-10-microsecond interval
implausible. The important limit is that we cannot credit or exclude the
delay as a cause from these captures.

Evidence: `artifacts/live/private/gpu-offline/gpc-link.c` around
`FUN_ffffff80032935a0`, `ident.c`, `ios81-postldr.c` around
`FUN_ffffff800329eb28`, `ios81-gpc-helpers.c` around `FUN_...32a1f4c` and
`FUN_...32a1f84`, `ios81-agx-disasm.txt` at the vtable entries, and
`artifacts/live/gpu/core-revision-20261107-test4.log` plus the associated
test4 clock-table/GPC/post-GPC captures.
