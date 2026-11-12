# J81 GFX provider trace: timing-record property correction

Offline examination of the local 19H394 kernel and the saved 19H394 iPadOS
PMGR registry snapshot. No device access or register operation. This corrects
the property name and row size in the older
[bcc56c timing-accounting note](2026-11-08-j81-ios15-bcc56c-timing-accounting.md).

## The optional source is `hw-dpe-reg`

In the decompiled ApplePMGR initializer `0xfffffff006bbf7a4`, the code
which creates the per-device timing records looks up a provider property
using the string at `0xfffffff005a55f65`. The bytes in the 19H394 image
resolve to `hw-dpe-reg`. If the lookup is null, the shown parser is skipped;
otherwise the path gets the property's bytes and length, and advances
through **0x28-byte rows**, not the 0x1c-byte rows described in the old
note. The row-derived objects are installed in the per-state/per-device
table used by the transition's `bcc56c` loop.

The local parsed 19H394 `ios-registry-runtime-20261111/pmgr.plist`
contains neither `hw-dpe-reg` nor `state-config` as an `IORegistry` key.
This is an after-boot snapshot of the queried PMGR entry, not a capture of
the exact object and property lookup at initialization. It supports—but
does not prove—that this optional parser was skipped on that boot. Another
provider, runtime-generated property, object binding, earlier state or
additional initializer remains possible. Absence of the old
`state-config` name alone was not the right discriminator.

## Why this matters

The optional records determine whether the inspected `bcc56c` branch can
be selected for GFX. The previously resolved gated action can read two
64-bit PMGR region-7 values, but this static path does not establish an
MMIO write or the GFX runtime index. Without evidence of `hw-dpe-reg` on the
actual provider or a live eligible record, the callback is a weaker lead for
the missing GFX setup than previously described. This is not proof that
no other PMGR callback or hardware side effect occurs, nor that the region-7
reads would be harmless.

## Evidence and next step

The relevant initializer begins its property check at the decompiled block
after `0xfffffff005a55f5f`; the property-name bytes at `0xfffffff005a55f65`
are `hw-dpe-reg`. It computes `length / 0x28`, reads the row state mask at
`+0x12`, and places pointers in the table based at object `+0x49b8`. The
transition loop and callback limits are in
[the callback audit](2026-11-11-j81-pmgr-bcc56c-callback-audit.md).

Before building a probe for this path, identify the exact provider/object
in the live IORegistry and whether the lookup or a qualifying GFX record
actually occurs. A zero trace without a positive control remains inconclusive.
More broadly, keep looking for an observed iOS operation missing from Linux;
this correction alone does not explain page-5 bit 30 or the GPU core stall.

Private evidence: `ios15pmgr-init.c`, the 19H394 kernelcache, and the PMGR
registry plist under `artifacts/live/private/`. The inspected 19H394 and
19H422 prelinked executable segments are byte-identical, but data and runtime
binding may differ; see [code parity](2026-11-11-j81-19h394-code-parity.md).
