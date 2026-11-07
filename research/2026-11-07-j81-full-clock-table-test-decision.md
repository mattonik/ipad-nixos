# J81 full 66-pair clock-table test decision

Do not run the full bridge-table write sequence yet. The offline path already
validates the 66-entry plan and models Apple's order (PMGR state 15, flush
index 100, selectors 9 then 10). The recovered plan and static evidence show
what Apple writes; they do not establish that replaying it from Linux is safe
or sufficient to prepare GPC.

## Evidence and limits

- Live writes have only covered selector 9 entries 0–4. Those writes completed
  under PMGR state 15, with GPC state 0 before the writes. There was no GPC
  post-read. Selector 10 and the other 61 entries remain unexercised.
- A prior GPC initialization reached state 1 using generic PMGR plus Fender
  writes, without the complete selector 9/10 action. A later RGX revision read
  still hung. The relationship between bridge-table replay and GPC/RGX
  readiness is therefore unresolved.
- The bridge value at `0x201f00018` has read back as `0x4` after writing
  `0x80010004` after a fresh PMGR transition with no bridge write, but the
  existing first-pair experiment then read back `0x80010004` after writing it
  and observed GPC still at 0. So the first word is retained in-session; its
  high bits' hardware meaning and effect on GPC remain unknown.
- `gpu-watchdog-supervisor` supervises a user-space child through stage output
  and host acknowledgements. If an MMIO access hangs in the kernel or stalls
  the interconnect, the child may stop emitting stages and the parent stops
  feeding the watchdog. That is a timeout/reset contingency, not proof that a
  wedged MMIO access is bounded or that the watchdog can recover a bus/core
  hang. No recovery record demonstrates a safe return from a hung bridge
  access.
- The existing `gpu_apple_clock_model.py` is execution-disabled and the
  offline model result explicitly says it is not authorization to replay the
  writes. Its private source plan is not a portable checked-in fixture, so a
  new test over synthetic values would only repeat structural checks and would
  not reduce the hardware safety uncertainty.

## Safe next step

Keep the work offline. Use the current model to validate the full private plan
and action order; do not add a live 66-write runner. Before considering any
larger hardware sequence, resolve the bridge readback/control-bit semantics
and establish an operator-present recovery procedure that accounts for a
stalled kernel MMIO access. Any subsequent hardware experiment should remain
one fresh-boot, one-pair-at-a-time with a post-write observation and an
explicit stop on timeout or unexpected state. The current evidence does not
justify proceeding to the remaining table entries.

The smallest discriminating observation already supported by the checked-in
tools has been performed: run `gpu-bridge-first` (which requires PMGR `0x3ff`
and GPC 0), then `gpu-bridge-peek` in the same boot. The captured result was
write `0x201f00018 <- 0x80010004`, GPC remained 0, and readback was
`0x80010004`; both watchdogs disarmed. This establishes the first address is
mapped, accepts and retains that word, and is readable. It does not identify
the meaning of the word or show any GPC state transition. The separate
read-only peek in fresh boots returned `0x4`, which is a different baseline
and cannot be compared as if it followed the write in the same boot.

Those captures used the verified RAM-boot Linux payload and PMGR module,
operator-present USB/TCP stage acknowledgements, exact probe/supervisor/wrapper
hash checks, rootfs-only mount checks, PMGR runtime-active/usage-1 checks, and
one-shot probe guards. Each capture file is exclusive-created. On timeout,
unexpected stage, or lost connection, the wrapper treats device state as
unknown; do not retry in that boot. The 20-second watchdog is a fail-safe only
if the hardware watchdog keeps running and can reset the device; it is not a
verified recovery mechanism for a hung MMIO transaction. Recovery therefore
means stop, wait for a fresh PongoOS/Linux handoff, re-establish the known
payload/module/PMGR state and confirm there is no stale one-shot state before
any separately authorized experiment.

No existing one-shot tool tests and reads back the next table address after
one new pair: `gpu-bridge-segment` writes five entries and has no readback,
while `gpu-bridge-peek` only reads `0x201f00018`. Therefore there is no new
one-step observation using only the current tools that discriminates the
remaining table effects. The existing first-pair result is the stopping point;
do not mistake the 20-second watchdog for guaranteed recovery if a new MMIO
access stalls the interconnect or kernel.
