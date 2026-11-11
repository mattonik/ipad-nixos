# J81 GPC request window: what another trace can distinguish

Offline review of the saved 19H394-associated AGX instructions, the iOS
control-boundary probe and Claude's Linux kernel-poll test. No iPad access.
The prelinked executable range was previously shown byte-identical in the
19H394 image, but this does not independently verify runtime binding.

The original iOS G4G path stores `0x11` to GPC `+0x1000` at
`0xfffffff006683998`, then executes a load and tests bit 4 in a loop at
`0x...399c`–`0x...39a0`. There is no function call or second store in that
same-thread instruction sequence. After the loop, the original code invokes
a delay, and then reaches the identity path. Interrupts, other CPUs, firmware
and autonomous hardware remain possible sources of activity. Thus tracing
only provider calls made by this thread during the request-to-poll interval
cannot identify an extra provider call there. This corrects the proposed
provider-focused trace as a primary explanation for that interval.

The control-boundary iOS probe does more than passively observe this sequence:
its `C` hook executes an additional PMGR read before the `0x11` instruction,
and its `M` hook calls the PMGR reader after the successful poll. Therefore
`C=0`, `M=0x40000000` establishes a difference between those observations,
not the instant the bit changed, nor that the original uninstrumented path
would see the same transition. The reduced iOS probe also observed a set
middle value with no `C` read, although it retained an earlier page-5 read;
that reduces, but does not remove, the concern about instrumentation.

Claude's Linux kernel-poll result on another boot recorded state 1 and page-5
zero less than 1000 ns later; that Linux probe sleeps between busy polls,
while the original iOS loop spins. Different polling rates, interrupt context,
MMIO mapping and prior hardware state are all potential differences, not
identified causes. In particular, the Linux sample does not rule out an
earlier short pulse. See the existing control capture and PR #38's
`research/2026-11-10-j81-gpc-page5-kpoll-test.md`.

## More useful discriminator

Before building a broader provider trace, inspect whether a small iOS hook can
record the **original** state-request store and successful poll, count or time
the original poll loop, and export only at the existing successful identity
logger. It should preserve the original instructions, register and flag state,
record explicit start and completion markers, and avoid any new MMIO reads.
A matching build/UUID and positive control are essential; a missing export or
no observed event is inconclusive. The hook itself changes loop timing, and a
counter or timestamp may add contention or trap in kernel context. Assess
those effects and interruption/reentrancy before implementation; timing and
poll counts are not proof of a clock, reset or bit-30 cause.

If measured iOS and Linux request-to-success intervals or polling patterns
substantially differ, a carefully supervised Linux comparison can test that
specific difference. Similar timing would not exclude a missing prior state.
A global trace of a proven PMGR writer remains useful only if it captures the
actual writer across threads with suitable coverage; the existing ordinary
writer trace has a positive site control but no matching entry and cannot
exclude aliases, other writers, or an in-flight race. Neither result alone
justifies writing page 5 or repeating the stalled GPU-core read.

Evidence: `artifacts/live/private/gpu-offline/ios15-agx-disasm.txt`,
`research/probes/j81-page5control/j81_page5control_shell.S`, the
[control and reduced iOS captures](2026-11-10-j81-page5-capture-results.md),
and the [writer capture](2026-11-11-j81-ios-page5writer-result.md).
Private captures and Apple binaries must remain private.
