# J81 ApplePMGR entry: GPC request investigation

Offline review following the 2026-11-15 entry-point controls. No new hardware
access. Private device logs and Apple binaries stay under `artifacts/live/private/`.

## What the controls establish

On iPadOS 15.8.5 (19H394), the entry-only hook ran and normal GPU firmware
startup followed. In separate temporary boots, the same entry hook mapped the
PMGR and two bridge regions, read GFX PS `0x300`, page-5 `+4 = 0`, performance
control `0x80000000`, VM `+0x23000 = 0xf01`, VM `+0x2300c = 0`, and PMGR
`+0x32000 = 0`. Powering GFX to `0x3ff`, writing the 66 bridge entries,
mapping GPC and reading its `+0x1000 = 0` each completed in staged controls.
With the first GPC write (`+0x10000 <- 0xffff0000`) or the first two (also
`+0 <- 0x40000000`), the completion marker and later GPU firmware-start marker
were recorded. Each result is from a different boot.

Two entry probes including the third write (`+0x1000 <- 0x11`) stalled after
kernel handoff. No checkpoints from either failed boot survived in the collected
archives and no new panic report was recovered. Neither result proves that the
third store was reached, that the transaction blocked, or that it returned and
a later operation or normal startup stalled. The three-write control returned
without polling; its earlier comparison controls used additional logging, so
execution timing and instrumentation also differ. Do not treat absence of a
log as a negative checkpoint.

A separate successful probe at the end of ApplePMGR `start()` used the power,
bridge and GPC recipe; it observed page-5 bit 30 set and core ID `0x00070500`.
Its pre-request VM word was `0x1`, versus `0xf01` at entry. Different point,
boot, and instrumentation: this is a candidate difference, not a causal proof.
Linux has also been observed with VM word `0x1` and still failed the GPU core
read, so that word alone is not an established Linux fix. The earlier success
probe's `G=30303000` must not be treated as verified GPC control readback: the
current inherited hook source reuses `x23` as the log-buffer cursor before the
purported GPC read. Binary/source correspondence for that historical run has
not been independently established.

## Normal iPadOS request: already observed

The documented 19H394-matched AGX sequence has a store of `0x11` at
`0xfffffff006683998`, followed directly by load/test polling at `...399c`–
`...39a0`; provider clock and power calls precede it. The identity path follows
successful polling and a delay. See `2026-11-11-j81-gpc-request-window.md` and
`2026-11-08-j81-ios15-g4g-pre-id-clock-power.md`; static branch and provider
interpretations retain the qualifications in those notes.

A previous normal-startup timing hook already bracketed the original store and
successful poll without adding MMIO reads. Its same-boot record was
`P1=000003ff T1=00001b1f I=00070500`, followed by GPU firmware startup
(`2026-11-11-j81-ios-gpc-timing-result.md`). Its approximate 289 microseconds
is conditional on the assumed 24 MHz timebase. Another instrumented boot saw
page-5 zero before the request and bit 30 set after the successful poll
(`2026-11-10-j81-page5-capture-results.md`). These traces do not prove what
sets the bit, establish an unperturbed timing distribution, or observe all
other CPUs and autonomous hardware. A new timing-only hook would mostly repeat
existing evidence.

## What this changes in the Linux plan

The entry campaign makes a raw early iPadOS replay a poor proxy for the Linux
failure: the third GPC request is valid in AGX's normal late path, but can
prevent a boot when injected at ApplePMGR startup. It should therefore not be
used to classify that write or page-5 bit 30 as a bad GPU setting.

The strongest remaining implementation boundary is the **clock-action
provider**, not another guessed MMIO word. The recovered GFX clock record is
ID `0x7c`, flags `0x06`, state index `100`, and selectors 9/10. Apple applies
the state change and selector tables through that provider and then performs
the flag-2 busy transition. The current Linux tree exposes only the generic
`apple,t7000-pmgr-pwrstate` domain: it has no device-clock record parser,
clock-state tracking, bridge-selector owner, or corresponding busy/tuner
notification. The manual diagnostic reproduced the PMGR state and table
stores, but not that ownership path.

This is a bounded engineering direction: model the fixed J81 GFX clock action
behind a disabled-by-default test interface, with one acquire/release owner,
strict state readback and rollback before any GPC request. It must not claim
that the busy/tuner action is electrically required until a paired test shows
a difference. The initial hardware test should stop after proving the model's
PMGR and bridge state; it should not read the GPU core.

## Rejected post-ADT bisection boundary

The `ApplePMGR::start()` instruction trace identifies four apparent
observation boundaries. They retain `x19 = ApplePMGR *` in static code and
occur immediately after the listed calls:

| Resume boundary | Preceding action |
| --- | --- |
| `0xfffffff006bb9808` | virtual `+0x598` ADT initialization |
| `0xfffffff006bb9818` | virtual `+0x5a0` |
| `0xfffffff006bb9828` | virtual `+0x5c8` |
| `0xfffffff006bb9838` | virtual `+0x5d0` |

The first proposed boundary, patching `0xfffffff006bb9810` and resuming at
`0xfffffff006bb9814`, is now rejected. Two 19H394 temporary boots panicked
after the resumed virtual call with the same data abort (`FAR 0x2728`). The
second was a no-op control: it made no logging, mappings, or MMIO accesses.
Therefore this is a hook/resume incompatibility, not evidence about PMGR or
the GPU. Do not use any of these mid-function boundaries for future capture.

Any iPadOS observation must instead use a previously boot-proven entry hook
with a return-path handoff, or a hook at a separately demonstrated safe call
boundary. It must first pass a no-op boot control before adding a read.

### Entry-return control result

The entry-return no-op control did boot 19H394 successfully. It preserves the
caller link register in a private 16-byte stack slot, replays ApplePMGR's
original prologue, then restores that link register after `start()` returns.
This establishes that the entry interception and return handoff are viable.

Adding one kernel log call at the return trampoline caused a distinct red-screen
reboot and a fresh data abort (`FAR 0x498`). Consequently, the handoff may not
call the kernel logger, mapper, or MMIO helpers. It is not an externally
observable capture channel yet. Do not iterate on return-time callback calls;
first establish a separately owned, non-reentrant recording transport.

The next request-bearing experiment is explicitly deferred until the snapshot
series identifies a candidate or a durable failure checkpoint is demonstrated.

## Best next offline work

1. Trace the exact 19H394 ApplePMGR `start()` calls between entry and success,
   prioritizing the code that clears VM `+0x23000` bits 11:8 and its actual
   caller/guards. List all MMIO writes and data dependencies along that path,
   clearly separating static candidates from observed runtime behavior.
2. Compare that write list with the recorded Pongo/m1n1/Linux initialization,
   including DWI state, voltage codes and ordering. Do not assume identical
   `+0x23000` readback proves all rails or timing match.
3. Audit persistent capture options before another failure-prone early boot:
   kernel logs flushed only after a successful boot cannot prove the last
   executed instruction. Any claimed persistent scratch location or external
   transport needs independently verified ownership, reset survival and a
   control; avoid inventing a persistent buffer or assuming a watchdog can
   recover a blocked bus transaction.
4. Design and prove an entry-hook return-path handoff before any more iPadOS
   capture. Its no-op control must boot on the exact 19H394 kernel.
5. If a candidate prerequisite is established, design a paired experiment
   with a known baseline and one change. A first-versus-third GPC write test
   without durable progress evidence can show only whether the whole boot
   completes; it cannot distinguish a stuck store from a later stall.

Private evidence includes `j81-entry-*-control-result/filtered.log`, the two
`j81-entry-gpc*-failed-result` captures and the earlier
`ios-logarchive-j81-pmgr-bisect-03` archive. Earlier successful GPC `G=`
interpretation should be corrected where published only after confirming the
exact binary provenance.
