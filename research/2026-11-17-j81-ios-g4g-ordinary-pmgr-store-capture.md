# J81: first ordinary PMGR store capture in the iOS G4G window

**November 18 coverage correction.** The 32 prefix rows and 17 tail rows
are visible samples across separate boots. The tail formatter reports staged
slots before a capacity-limited merge. Ordinary rows carry synthetic thread
and instance labels. The published counts therefore leave the presence of
a GFX state-word store in the working transition unresolved.
[Exact-build review and builder handoff](2026-11-18-j81-gfx-transition-builder.md)

## Result

The reduced 19H394 iPadOS probe completed normally and the device reached
the unlocked home screen. Its export contained 32 ordinary PMGR store
requests during the global clock-provider observation window. The producer
stages ordinary writer arguments before the displaced store instruction.

## Captured prefix

The formatter supplies the instance tag `0x80000000` for every ordinary row.
The runtime instance and executing thread are unknown.

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
`AppleT7001PMGR` decompilation.  `FUN_fffffff006c8a0c4` walks offsets
`0x22000` through `0x22180` in steps of `0x10`, writes each existing word with
bit 31 selected according to its platform condition, skips `0x22030` through
`0x22070`, and explicitly skips `0x22120`.  That is the exact inclusion and
omission pattern in the live capture.  This is an ordinary PMGR control-bank
operation, not a reconstructed GPU-core write.

The `0x20100`, `0x20108`, `0x20110`, and `0x20120` offsets are PMGR
power-state-table slots 32, 33, 34, and 36 respectively (`0x20000 + 8*i`).
J81 GFX is state index 100, at `0x20320`.  Therefore the captured prefix
does not yet contain a direct write to the known GFX power-state word.  The [J81 domain lookup](2026-11-18-j81-gfx-state-word-comparison.md)
identifies these four offsets as LIO, IOMUX, AIC and DWI.

## Second bounded slice

A second successful boot skipped the first 32 events. Its export shows
17 ordinary rows at `0x20120`, `0x20128`, `0x201a0` through `0x201e0`,
and `0x201f0`. The printed values include `0x000000ff` and `0x100000ff`.
No printed row identified GFX. In the skip-32 producer, `O00000020`
means 32 staged slots before the capacity-limited export. Confirming
the archived binary matches that producer would leave 15 slots unexplained.
The earlier `O00000113` came from a different build. Interpret its O
field only against that build's formatter.

## Next measurement

Recover the actual GFX request and poll from one attributable transition.
The 32 prefix and 17 tail rows came from separate boots and establish no
requirement to reproduce the visible UART or MCC operations. See the
[builder handoff](j81-gpu-builder-handoff.md).

Evidence: retained private `boot.logarchive` files from the successful
2026-11-17 10:24 and 10:45 local iPadOS boots; the generic-writer
`O00000113` result; and [the prior transition-gap review](2026-11-16-j81-pmgr-transition-gap.md).
