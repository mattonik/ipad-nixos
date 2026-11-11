# J81 tuner probe: positive-control feasibility

Offline follow-up to the [zero-marker result](2026-11-11-j81-ios-tuner-result.md).
No device access. Claude's published PR #38 ended at the PMGR word sampler
when checked; unpublished work in another session is not visible here.

## Existing call chain

Earlier work in [the November 4 trace](2026-11-04-j81-gpu-offline-trace.md)
already resolved more of the tuner chain than the later short SoC-tuner note
reported: `ApplePMGRNub` prepares device-set bitmaps; gated action
`0xfffffff006bdc648` dispatches message 10 through an object's `+0x420`
slot; `0xfffffff006cd8ab0` checks that message and dispatches the supplied
bitmap pointer through tuner slot `+0x548`.

In the actual 19H394 kernel's `__PLK_DATA_CONST`, the constructor-installed
tuner vtable candidate `0xfffffff006ffc548` has `+0x420` =
`0xfffffff006cd8ab0` and `+0x548` = `0xfffffff006cd827c`, exactly the
entry instrumented by the tuner probe. The same candidate table has
`+0x550` = `0xfffffff006cd840c`, `+0x558` = `0xfffffff006cd83e8`,
`+0x560` = `0xfffffff006cd8410`, and `+0x568` =
`0xfffffff006cd8414`. These are static pointer values, not proof that the
object reached at runtime has that vtable or that the action is called.
The decoder output for `bdc648` and `cd8ab0` is in the private
`gpu-offline/ios15pmgr-tuner-callback.c` and `ios15soctuner-event-insn.log`.

The device-set inputs described by the earlier trace support this as the
right *candidate policy handler*, not a concrete safe event that forces it
to run. The static chain still does not establish whether the action ran
before GPU identity, whether it completed asynchronously, or whether any
selected MCC operation affected the GPU. The November 8 note's statement
that the PMGR-to-tuner notification path was unresolved should be read with
the more complete November 4 trace; runtime ordering remains unresolved.

## Why a later event needs a different observer

The tuner probe only prints its accumulated flags at the existing GPU
identity hook. A tuner event after that point cannot appear in the already
emitted `U` line; asking the user to change brightness or wait on this boot
would not by itself retrieve later flags. Moreover, the available code does
not prove a brightness change necessarily generates the relevant PMGR
device-set transition. The instrumented `U` output supports the main probe
having run, but does not independently demonstrate that the policy entry or
return hook was reached during this boot before the snapshot. Missing flags
remain inconclusive, including due to concurrency and lifecycle ordering.

To establish a positive control, first identify a later, source-backed event
and an existing safe log/export point after it. The observer must preserve
thread/phase attribution, explicitly handle asynchronous completion, and not
call the logger inside an unknown interrupt or command-gate context. Before a
new boot, test the exact build, hook installation, publication and retrieval.
No such trigger or validated later export point is established yet.

## Bridge readback alternative

The existing [bridge consumer trace](2026-11-07-j81-bridge-window-consumer-trace.md)
finds no iOS readback or register-field contract for the `+0x40000` table
words. The first `+0x18` address has Linux readback history, but its high
bits have also been observed changing across contexts; the
[encoding note](2026-11-06-j81-bridge-encoding-conclusion.md) does not
establish their semantics. Do not select another of the 65 unverified words
solely because it appears in the table. A promising experiment still needs a
documented safe read and a comparison whose outcome distinguishes causes.

Private full kernel images and device logs stay local. No new hardware test
or register operation follows from this audit.
