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
printed 32 ordinary requests on one boot and 17 on the other. None of the
printed offsets is the GFX power-state word at PMGR region-0 `+0x20320`.

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

## Combined capture

The November 17 build kept the observation window open across the existing
clock and power actions and exported its sample after the power action.

## Hardware result

The 19H394 power-window probe booted successfully on 2026-11-17 at 12:01
local time. Its logger runs only from the new power-callback wrapper, after
that callback returns. It emitted the same 17 direct-store rows seen in the
previous clock-tail capture (`+0x20120`, `+0x20128`, `+0x201a0` through
`+0x201e0`, and `+0x201f0`) and no further row. In particular, it did not
observe `+0x20320`.

The result establishes which rows survived the combined-window export.
The recorder can fill before the power action, and the merge can omit staged
rows. The number of additional GFX requests in the power action remains
unknown. The [builder handoff](j81-gpu-builder-handoff.md) asks for per-boot
accounting and a trace filtered to the GFX offset.

Evidence: 19H394 `ios15-agx-disasm.txt` at
`0xfffffff006683918..68399c`, and the two successful direct-store captures
documented in [the callback capture](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md).
