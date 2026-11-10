# J81 GPU: next discriminating test and build-agent handoff

## Objective and established facts

Find whether Linux briefly produces the iPadOS-observed page-5 bit 30 around
GPC state 1. This is an experiment about timing, not a GPU driver or proof
that the bit controls the stalled GPU core. Do not write `0x20e005004` or
read the GPU core in this experiment.

- On iPadOS 15.8.5 19H394, the page-5 method read was `0` after the
  power-provider return and at the pre-GPC-state-request checkpoint; the
  sample after the successful GPC poll was `0x40000000`. The GPC poll was
  `1`, identity `0x70500`, and firmware boot was reported. Buffered result
  lines are emitted later and must not be interpreted in log order. Physical
  mapping is inferred from Pongo ADT, not independently measured in iOS.
  See [iOS captures](2026-11-10-j81-page5-capture-results.md#gpc-control-boundary-transition-after-control-sample).
- On a separate Linux boot, the guarded GFX cycle, 66 bridge stores and GPC
  setup completed. GPC poll was `1` at poll 5; a one-shot page-5 read in the
  same process returned `0`. A timestamp taken after poll to sysfs return was
  34.5 µs, but time between the MMIO poll and that timestamp was not measured.
  The watchdog disarmed. See [Linux capture](2026-11-10-j81-linux-gpc-page5-timed-probe.md#corrected-hardware-result).
- `0x20e005004` bit 30 is not an input to the specific LLB rate calculation
  analysed here. No evidence establishes that this bit is writable, required
  for GPU readiness, or has no read side effects. See [rate analysis](2026-11-10-j81-page5-bit30-rate-analysis.md).

## Hypotheses and falsifiable results

**H1: short Linux transition.** Bit 30 can be set immediately at successful
GPC polling but is clear by the existing userspace/sysfs sample. A first
kernel-side sample with bit 30 set, followed by a clear later sample on the
same boot, supports H1. A zero first sample argues against H1 only at that
observed instant, not at earlier instants between write and poll. A missing
sample, failed poll, or lost capture is inconclusive.

**H2: different state or mapping.** The immediate Linux sample remains zero.
A repeated successful zero would strengthen that observation, but would not
identify the cause. Investigate the runtime region/mapping and hardware/boot
prerequisites next; don't infer that setting bit 30 is safe or sufficient.

**Control: read effects and timing.** Two reads can themselves change state;
a transition between them has multiple possible causes. If feasible, compare
on separate fresh boots against a delayed-only one-shot using identical GPC
setup. A difference between paired and delayed-only observations is evidence
of instrumentation/timing sensitivity, not proof of a destructive read.

## Implementation and validation requirements

1. Start with `kernel/page5-read-once/page5-read-once.c`,
   `boot/gpu-gpc-page5-timed.c`, the v2 campaign and its existing tests. Design
   a bounded module/test that makes a **first page-5 read in kernel context
   as close as practical to the successful GPC poll**, and records one later
   page-5 read only if the repeated-read control is implemented and reviewed.
   Avoid `/dev/mem` for page 5: the existing module maps the PMGR-owned region.
   Report the exact instructions/timestamps used; don't call a measurement
   immediate or an upper bound unless its start and end actually bound it.
2. Retain exact J81, page size, kernel notes/module hash, fresh boot ID,
   active runtime lease, RAM root and one-shot guards. Require host
   acknowledgment before the combined, irreversible GPC-write/read batch;
   preserve the fail-closed watchdog. Publish and flush a pre-batch marker
   before starting. If logging between poll and read would disturb timing,
   buffer the sample and explicitly document that a stall may lose it.
3. Poll GPC with the validated paced bounded loop. Report the raw poll and
   count on failure. First version's tight polling failed without a final raw
   value; don't use a missing result as zero. Use normal Linux MMIO accessors,
   documented barriers, and explicitly account for preemption/interrupts.
   Do not assert hard realtime timing from a software timestamp.
4. Review mapping/resource ownership and possible read side effects. One
   kernel context containing both GPC polling and page-5 read may require new
   mappings; only use known J81 ranges and document ownership. Do not claim
   the Apple control-write branch executed merely because its location was
   passed, or that stores persisted from after-write checkpoints alone.
5. Add host tests for address/order, one-shot behavior, failed mapping,
   invalid GPC state, busy timeout, output parsing, watchdog/host disconnect,
   and wrong kernel/boot/hash. Build against the exact existing 7.3.0-rc1
   kernel tree and verify module vermagic and notes. Do not run the test until
   its preflight, actual binary/module hashes and fresh-boot workflow are
   checked. If a stall is possible, explain recovery and what output may be
   lost. Never perform an extra core read or change page-5 bits automatically.

Reference workspace: `/Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos`.
The full iOS logs, binary images and hardware logs are private; publish only
bounded findings, source code and non-identifying summaries. There is no need
to copy private Apple binaries or device log archives into Git.
