# J81 iPadOS GPC timing capture

On 2026-11-11 the temporary 19H394
[GPC timing probe](probes/j81-gpc-timing/README.md) booted iPadOS. The module
SHA-256 was `bb36d637c7659215e747ed734c78587dc55a0a4154d708bcc8bc26297549c9c5`.
The startup archive contained the probe record:

```text
P1=000003ff T1=00001b1f I=00070500
```

The `T1` marker indicates that the matching start and finish hooks recorded a
valid 32-bit delta of **6,943 mach absolute-time units**. `P1` is the captured
PMGR poll value and `I` is the already-existing GPU identity read; the same
boot later logged G4G A1 and successful GPU firmware startup. The timing hook
did not add a GPC, GPU or PMGR MMIO read, but inherited provider hooks and the
two timer calls perturb execution. Firmware startup is not a rendering test.

The saved Pongo ADT reports a 24 MHz timebase. **If** it also describes the
running 19H394 mach absolute-time scale, 6,943 units is approximately
**289.3 µs**. The iPadOS timebase conversion has not been measured in this
boot, so this is a conditional conversion, not a verified duration.

For context, Claude's earlier Linux kernel-poll experiment reported
`postwrite_ns=291125` and `prewrite_ns=291916`, i.e. approximately
291.1–291.9 µs around its successful poll on a separate boot (PR #38,
`research/2026-11-10-j81-gpc-page5-kpoll-test.md` on the PR branch). Under the
24 MHz assumption the numbers are close on these individual boots. They are
not equivalent timestamps: iOS measures from before the state-request store
to after the successful loop branch, while Linux brackets the store and takes
its success timestamp before the poll load. Instrumentation, IRQ handling,
polling strategy, scheduling and prior state differ. They are single samples,
not distributions, and neither proves identical hardware transitions.

This weakens a hypothesis that a large request-to-success timing difference
is required to explain the observed iOS/Linux page-5 discrepancy. It does not
exclude a brief pulse, a smaller timing difference, other state differences,
or show that page-5 bit 30 controls GPU readiness. The probe did not sample
page 5 and does not establish the cause of the Linux GPU identity stall.
Do not infer that a GPU-core read or a page-5 write is now justified.

Raw archive and decoded kernel log remain private under
`artifacts/live/private/ios-logarchive-j81-gpc-timing-01/`.
