# J81: first ordinary PMGR store capture in the iOS G4G window

## Result

The reduced 19H394 iPadOS probe completed normally and recorded the first 32
ordinary PMGR stores made while the existing G4G clock-provider callback was
active.  The count-only predecessor recorded **275** such stores on a
successful boot.  This is the first positive evidence that the iOS transition
does materially more than the 66 selector-9/selector-10 bridge writes already
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

## What this changes

The current raw replay contains the bridge-store family but not this ordinary
PMGR sequence.  It can therefore reach GPC state 1 while leaving one or more
dependent clock, rail, reset, or fabric transitions incomplete.  That matches
the observed permanent stall of the first RGX identity read in Linux and
PongoOS.

This does **not** identify a safe write sequence yet:

* the 32 rows are only a prefix of 275 calls and may include shared transition
  work unrelated to GFX;
* the capture gives method arguments, not verified physical addresses or
  register meanings; and
* blindly replaying the whole prefix would mix unknown PMGR state-machine
  operations with Linux boot state.

## Next discriminator

Statically trace the ordinary PMGR mapping family for these offsets and
identify which correspond to the active GFX dependency chain.  Then capture a
bounded later slice (or a filtered subset) around the PMGR entries linked to
GFX rather than expanding a blind replay.  The first hardware replay, if
justified, should be a single mapped, read-back-checked state transition with
the existing watchdog/recovery procedure—not all 32 writes.

Evidence: the retained private `boot.logarchive` from the successful
2026-11-17 10:24 local iPadOS boot; the count-only `O00000113` result; and
[the prior transition-gap review](2026-11-16-j81-pmgr-transition-gap.md).
