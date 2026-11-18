# J81: the remaining ordinary-PMGR capture window is the power callback

**November 18 coverage correction.** The 32 prefix rows and 17 tail rows
are visible samples across separate boots. The tail formatter reports staged
slots before a capacity-limited merge. Ordinary rows carry synthetic thread
and instance labels. The published counts therefore leave the presence of
a GFX state-word store in the working transition unresolved.
[Exact-build review and builder handoff](2026-11-18-j81-gfx-transition-builder.md)

## Finding

The two successful direct-store captures bracketed only the first iOS 15 G4G
provider callback, the clock action at `0xfffffff006683918..683930`.  They
observed 49 completed ordinary ApplePMGR stores and no GFX power-state word at
PMGR region-0 `+0x20320`.

That result does **not** cover the immediately following power action.  The
same exact G4G probe executes:

1. provider vtable `+0x568(1, 0)` at `0x...3918..3930`;
2. provider vtable `+0x570(1, &out, 0)` at `0x...3934..394c`;
3. only then the GPC writes and RGX identity read.

The current hook arms the direct-store recorder before the first `blr x8` and
clears it when that call returns.  It necessarily excludes the second `blr
x8`.  Therefore absence of `+0x20320` in the existing two slices is evidence
about the clock callback only, not a negative result for the complete iOS
power transition.

## Next safe probe

Extend the already proven two-hook direct-store probe with one exact G4G
call-site wrapper at the power call.  Keep the recorder armed across the
clock return, and clear it only after the power callback returns.  The store
trampoline remains unchanged: it executes the displaced ordinary-store
instruction once and records its arguments after that instruction, without
adding an MMIO read or write.

The wrapper must reject anything but the exact 19H394 UUID and both unique
call-site signatures.  Before device use it needs host cases for:

* clock-only execution: no stale active flag;
* clock followed by power: ordinary stores in both calls are retained;
* unrelated stores outside both calls: omitted; and
* duplicate/capacity handling.

No PMGR or GPU register will be written by the probe.  It should be run as a
temporary iPadOS boot, not from Linux or PongoOS.  A nonempty power-window row
outside Linux's already replayed bridge tables gives a concrete, mapped
candidate for a later single-transition comparison.  An empty result only
rules out ordinary stores in these two callbacks; it does not prove the core
is ready or authorize another RGX identity read.

## Hardware result

The 19H394 power-window probe booted successfully on 2026-11-17 at 12:01
local time. Its logger runs only from the new power-callback wrapper, after
that callback returns. It emitted the same 17 direct-store rows seen in the
previous clock-tail capture (`+0x20120`, `+0x20128`, `+0x201a0` through
`+0x201e0`, and `+0x201f0`) and no further row. In particular, it did not
observe `+0x20320`.

Because the hook remained armed across both callbacks and emitted only after
the second, this is positive evidence that the second provider callback added
no completed entry at the intercepted ordinary ApplePMGR store site. It rules
out the specific hypothesis that the missing transition is an ordinary-store
operation in the power callback. It does not rule out a different PMGR method,
direct MMIO, asynchronous work, or state established before either callback.

The next investigation should be static and target those distinct paths; a
third window at this same store site would only repeat the now-bounded result.

Evidence: 19H394 `ios15-agx-disasm.txt` at
`0xfffffff006683918..68399c`, and the two successful direct-store captures
documented in [the callback capture](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md).
