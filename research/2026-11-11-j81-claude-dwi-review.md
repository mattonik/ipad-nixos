# J81: review of DWI and performance-state experiments

Review of PR #38 at `30ed203`, plus the subsequently collected private
`pmgr-words` captures. No additional device access was performed here.

## What the captures establish

The 19H394 iPadOS log records `0x80000000` at the early, power and control
checkpoints and `0x80110100` after the GPC poll for PMGR `+0x1c200`. The
Linux capture reports the same corresponding values. This disproves the
earlier suggestion that `0x80110100` alone indicated a Linux-only pending
transition; it does not prove every rail or clock is ready.

The iPadOS table probe measured `0x6436d063` and `0x70` at `+0x1c010` and
`+0x1c014`, matching earlier Linux reads, and `0x40000001` at `+0x1c300`.
The Linux DWI-first capture shows power state `0x200` changed to `0xff`,
GPC state 1 on poll 11, and page-5 `+4` equal to zero within 750 ns of the
successful poll; a subsequent DWI power-state read was `0xff`. Turning on
that power state before the request therefore did not reproduce the iOS
page-5 bit in this run. It does not establish DWI protocol or PMU state.
These are snapshots at selected points, not proof that every PMGR word or
the full transition sequence is identical. In particular, matching two
table words does not prove the whole iOS performance table was unchanged.

## DWI configuration lead

After the DWI-first test, Claude captured `0x00000001` and `0x0000003c` at
physical `0x20e200000` and `0x20e200004`, respectively. The same capture
reports DWI power state `0xff`. The saved iOS 8.1 J81 ADT names a DWI node
at child address `0x0e200000`, size `0x1000`; the previously established
arm-io translation gives this physical base. Its properties include
`nclk-div=1`, `polarity-config=1`, `lockout-us=5`, and `str-delay=8000`.
The values do not establish their register fields or prove a protocol works.

The private static MMIO scan of the separately analyzed 15.x LLB reports
stores to those same two addresses in `FUN_1803981c8`; its decompilation
shows the two written values are computed from clock and configuration
inputs. This is evidence against assuming the registers are necessarily
left untouched before Linux, but not evidence of their exact values on the
current iPadOS boot or that this LLB path executed. No iPadOS runtime read
of those two DWI words has been found. Compare the same words at equivalent
boot points before calling them a difference. The existing iOS probe's
ordinary PMGR region-0 reader is not established to cover the DWI node;
do not simply pass `0x200000` to it.

## Review observations

- `pmgr-words-peek` is read-only in the C access mode, but permits any
  aligned offset in the first `0x40000` bytes, plus two DWI offsets. MMIO
  reads can have side effects or stall. The DWI-on prerequisite appears
  only in a comment, not as a runtime check. Use only individually justified
  addresses with recorded preconditions; do not treat it as a safe scanner.
- The PR description and the perftab README have not caught up with the
  additional hardware runs. PR #38 remains open; it includes the two
  later probes and DWI tools as well as its original kpoll scope.
- Host tests for the read-only sampler, DWI writer, kernel poll module and
  host capture passed during this review. They mock hardware and do not
  prove power-domain safety or register semantics.

The private raw captures are under `artifacts/live/gpu/pmgr-words-20261111-*`
and `artifacts/live/private/ios-logarchive-j81-perfctl-03/` and
`ios-logarchive-j81-perftab-01/`; do not publish full device archives.
