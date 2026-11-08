# J81 next MCC/GPU experiment decision (2026-11-08)

Offline decision note after the supervised MCC read returned zero. No device,
firmware, or MMIO was used to prepare this comparison.

## Decision

Do not schedule a second MCC read, an MCC selector write, or another GPC/core
read as the immediate next experiment. The MCC value `0x00000000` is a valid
raw Linux observation at `0x200000830`, but it establishes neither MCC
initialization/ownership nor iOS callback history. The previous GPU revision
read at `0x201000020` did not return after its `before` checkpoint. There is
no source-backed, bounded live experiment in the present evidence that would
turn either outcome into a causal diagnosis.

The next useful step is offline: identify a concrete source or runtime
observation for Apple's pre-ID provider clock edge and the state that gates
the MCC callback. Revisit hardware only if this yields a specific,
independently observable transition and an access known to be safe in that
phase.

## Candidate comparison

| Candidate | Information it can add | Causal value | Hardware risk | Decision |
|---|---|---|---|---|
| Repeat read of MCC `+0x830` | Repeatability of a raw Linux value, if run in a new boot; a repeated zero still cannot identify who initialized or wrote it | Very low: no independent selector/callback event is bracketed | Lower than a write, but the completed one-shot proves only that this access completed once; Linux does not own/publish the range and hardware response/safety is undocumented | Defer. Do not spend another boot on an unbracketed repeat. |
| Controlled selector-3 write | Could produce the driver's display-on write signature (`value & 0x11f == 0x10a`) if the source-derived RMW reaches the block | Low without an independently observed Apple callback and known initialized state; a matching post-value still cannot prove acceptance or functionality | Highest MCC option: undocumented bits, unknown initialization/power state, and an active write to live cache/display control. Selector 3 is not established as a safe Linux operation | Reject. Do not translate the iOS selector into a Linux MMIO recipe. |
| GPC/core probe | A GPC state observation may repeat already captured state; another core-ID read would target the exact transaction that stalled in test4 | Low: PMGR `0x3ff`, GPC state/control, and bridge state are already recorded; these do not establish Apple's provider reference edge or explain why RGX `+0x20` failed | GPC reads may be low-risk only at a demonstrated phase; the core read is known to hang, and the firmware hold/state-zero sequence is not shown on the pre-ID call path | Stop core reads and do not replay hold. No new GPC address is justified by current source. |

Selector values here are conditional software effects, not hardware mode
definitions. Selector 3 is the display-on table entry; its expected mask
signature is recorded in
[`2026-11-08-j81-mcc-read-result.md`](2026-11-08-j81-mcc-read-result.md).
The exact software RMW path and semantic limits are in
[`2026-11-07-j81-mcc-ios81-record-stride.md`](2026-11-07-j81-mcc-ios81-record-stride.md)
and [`2026-11-07-j81-mcc-hardware-meaning-audit.md`](2026-11-07-j81-mcc-hardware-meaning-audit.md).

## Causal boundary and stop rules

* The zero MCC word matches none of the recorded low-five-bit/bit-8 selector
  patterns. It does **not** prove MCC is off, uninitialized, or that selector
  0/3/4 did not run: this Linux boot has no established MCC ownership or iOS
  execution history.
* Selector 3/4 effects require several runtime guards, including the SoC-busy
  edge, display callback success, MCC object/guard availability, and the
  controller startup marker. The wrapper can report success despite the
  controller marker preventing writes. None of those values was observed.
* Test4's table/GPC readbacks do not establish Apple's provider
  `enableDeviceClock`/`enableDevicePower` calls or its software reference
  transition. Conversely, the missing callback is a software-path delta, not
  evidence that it caused the core read stall. The distinct firmware hold
  method is not proven to precede the early identity read.
* Stop live work on MCC writes, guessed clocks/resets, address scans, and
  repeated `0x201000020` reads. A stopped/hung access is not safely rescued
  merely because a host watchdog was armed; test4 lost USB after the stalled
  read and did not establish watchdog recovery.
* Reconsider a live experiment only with (1) an identified and bounded source
  path or independently observable callback event, (2) a justified register
  and phase, (3) read/write safety evidence for that phase, and (4) a capture
  that distinguishes the competing causes without relying on the result of a
  known-hanging access.

Evidence: the Nov. 8 single-read result; the MCC hardware-meaning audit; the
Nov. 7 display/MCC ordering trace; the GPC hold boundary; and test4's
core-revision result. This note adds no claims about hardware register
semantics.
