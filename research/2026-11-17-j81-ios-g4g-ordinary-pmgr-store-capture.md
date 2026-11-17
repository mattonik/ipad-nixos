# J81: first ordinary PMGR store capture in the iOS G4G window

## Result

The reduced 19H394 iPadOS probe completed normally and recorded the first 32
ordinary PMGR stores made while the existing G4G clock-provider callback was
active.  This is the first positive evidence that the iOS transition does
materially more than the 66 selector-9/selector-10 bridge writes already
replayed by Linux and PongoOS.

The capture observes the ordinary ApplePMGR store path (virtual `+0x988`),
executes its displaced instruction unchanged, and copies only completed-entry
arguments after the callback returns.  It performs no added MMIO operation.
The boot reached the unlocked iPadOS home screen.

## Captured prefix

The capture labels these as ordinary stores with a high bit on the displayed
instance.  The real instance is zero in every row below; `0x80000000` is just
the probe's provenance tag and is not a hardware argument.

| PMGR region-0 offset | Value | Observed occurrences in first 32 |
| --- | ---: | ---: |
| `0x1008` | `0x40480348` | 1 |
| `0x4008` | `0x48480348` | 1 |
| `0x22000` | `0x80000000` | 1 |
| `0x22010` | `0x80000000` | 1 |
| `0x22020` | `0x80000000` | 1 |
| `0x22080` | `0x80000000` | 1 |
| `0x22090` | `0x89070300` | 1 |
| `0x220a0` | `0x89040300` | 1 |
| `0x220b0` | `0x89060300` | 1 |
| `0x220c0` | `0x89040300` | 1 |
| `0x220d0`–`0x22110`, `0x22140`, `0x22160`–`0x22180` | `0xc9040300` | 10 |
| `0x22150` | `0xa4080800` | 1 |
| `0x22160`–`0x22180` | `0xc9040300` | 3 |
| `0x20100` | `0x0f0000ff` twice, then `0x1f0000ff` | 3 |
| `0x20108` | `0x0f0000ff` twice, then `0x1f0000ff` | 3 |
| `0x20110` | `0x000000ff` twice, then `0x100000ff` | 3 |
| `0x20120` | `0x000000ff` twice | 2 |

`0x1008` and `0x4008` are consistent with the separately observed iOS
GPU-window bit-30 activity, but this capture is of PMGR region 0.  Equal
offsets or bit patterns must not be treated as the same register without an
address-mapping proof.

## Static classification of the first slice

The `0x22000` block is now classified from the matching local 19H394
`AppleT7001PMGR` decompilation.  `FUN_fffffff006c8a01c` walks offsets
`0x22000` through `0x22180` in steps of `0x10`, writes each existing word with
bit 31 selected according to its platform condition, skips `0x22030` through
`0x22070`, and explicitly skips `0x22120`.  That is the exact inclusion and
omission pattern in the live capture.  This is an ordinary PMGR control-bank
operation, not a reconstructed GPU-core write.

The `0x20100`, `0x20108`, `0x20110`, and `0x20120` offsets are PMGR
power-state-table slots 32, 33, 34, and 36 respectively (`0x20000 + 8*i`).
J81 GFX is state index 100, at `0x20320`.  Therefore the captured prefix
does not yet contain a direct write to the known GFX power-state word.  It
does demonstrate that the provider window drives additional platform PMGR
work around the GFX transition.

## Second bounded slice: callback tail

A second successful boot skipped the first 32 stores and recorded the next
window.  It produced 17 completed ordinary-store rows before the callback
returned: `0x20120`, `0x20128`, then state-table slots `0x201a0` through
`0x201e0`, followed by `0x201f0`.  The repeated `0x000000ff` / `0x100000ff`
pairs are the same PMGR power-state-table pattern seen in the prefix.

There was no `0x20320` row (J81 GFX, state index 100).  More importantly, the
second hook's `O00000020` header is its *merged log-record* count, not its
ordinary-store count.  Only the 17 `P1T1` rows are direct evidence for this
window.  The callback therefore contributes 49 observed ordinary stores to
this hook invocation, not an observed 275.

The earlier count-only result, `O00000113`, came from different
instrumentation and cannot now be interpreted as 275 stores from this one
callback.  It may include other PMGR paths or callback invocations.  It remains
useful as evidence of broader PMGR activity during the boot, but not as a
bound for this safe callback-local capture.

## What this changes

The current raw replay contains the bridge-store family but not this ordinary
PMGR sequence.  It can therefore reach GPC state 1 while leaving one or more
dependent clock, rail, reset, or fabric transitions incomplete.  That matches
the observed permanent stall of the first RGX identity read in Linux and
PongoOS, but does not yet assign causality to this particular control-bank
routine.

This does **not** identify a safe write sequence yet:

* the 49 callback-local rows observed across the two windows may include
  shared transition work unrelated to GFX;
* the capture gives method arguments, not verified physical addresses or
  register meanings; and
* blindly replaying the whole prefix would mix unknown PMGR state-machine
  operations with Linux boot state.

## Next discriminator

Resolve the count-only/callback-local scope mismatch offline before capturing a
third numerical window: this callback's observed tail ends before GFX index
100, so a third `65..96` window has no demonstrated chance of producing a
GFX row.  Do not replay the `0x220xx` bank: it is a platform PMGR routine whose
GFX necessity is not established.  Any eventual first replay must be a single
mapped, read-back-checked state transition with the existing watchdog/recovery
procedure—not the captured prefix wholesale.

Evidence: retained private `boot.logarchive` files from the successful
2026-11-17 10:24 and 10:45 local iPadOS boots; the count-only `O00000113`
result; and [the prior transition-gap review](2026-11-16-j81-pmgr-transition-gap.md).
