# J81 page-5 transition: next measurement boundary

The paired 19H394 boot measured PMGR-method offset `0x5004` as `0` just
following the first GFX clock-provider return and `0x40000000` after the
original GPU identity loads. See the [capture](2026-11-10-j81-page5-capture-results.md#paired-ios-4-timing-on-one-boot).
The times are log timestamps; the register reads and logging can perturb the
path. The responsible operation and register semantics remain unknown.

The previously analysed iOS 15 G4G path places these actions between the
checkpoints (addresses in that report are from its 15.8.8 disassembly, not
asserted as 19H394 addresses):

1. Provider power request (`+0x570`), after the clock call (`+0x568`).
2. GPC setup writes, then its state poll and a 10 µs delay.
3. GPU identity dispatch and its original `+0x20`, `+0x18` reads.

See [the pre-ID trace](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md).
The 19H394 probe already hooks the GPC poll and captured its successful
value `1` in the same paired run. That hook is the best next intermediate
boundary: sample offset `0x5004` once after the GPC poll succeeds and before
the identity dispatch, with the existing early and late reads as controls.

If the intermediate sample has bit 30 set, the transition is observed by
the poll-success boundary, after the early provider-return sample; this does
not distinguish power request, GPC writes, time or concurrent activity. If
clear, the transition is observed after that sample and by the late sample,
which includes delay and GPU identity reads. Either outcome narrows the
observed window, but the additional read could itself alter state. Missing
markers or a skipped poll are inconclusive. A follow-up at the power-provider
return would distinguish earlier subintervals only if warranted.

This is a proposed measurement, not a prepared or tested hardware probe.
The existing poll hook executes inside a loop and currently saves only the
already loaded register. Calling the PMGR read there requires a fresh audit
of register and flags preservation, stack and interrupt context, reentrancy,
object lifetime, first-success single-shot behavior, and safe logging or
buffering. Host simulations and the exact-build signature guards must pass
before a device run. Full log archives stay private. No Linux write or GPU
core access is justified by this comparison alone.

An experimental [intermediate probe](probes/j81-page5middle/README.md) has now been built and host-tested, but still requires independent context and preservation review before any device run.
