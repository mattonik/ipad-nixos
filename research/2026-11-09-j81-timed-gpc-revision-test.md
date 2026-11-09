# Prepared J81 timed GPC-to-revision experiment

> **First execution stopped before the core read.** Use the [revised v2 plan](2026-11-09-j81-timed-gpc-revision-first-result.md) for a future boot.

Prepared offline on 2026-11-09. This is a one-shot experiment, not a verified
GPU initialization sequence. The operator explicitly requested preparation
even with the known stall risk. It has not been executed on hardware.

## Question and limits

Test4 initialized GPC and attempted the core revision read in separate,
host-mediated runs; the exact gap was not captured. This experiment repeats
the same PMGR and 66-pair bridge setup, but puts GPC initialization, the
successful state poll, a delay of **at least** 10 microseconds, and one
32-bit revision read in the same process. A successful read would show that
this sequence can reach the identity register on that boot; it would not
prove the delay was the cause. A repeated stall would show only that this
particular short-gap attempt did not return. Userspace scheduling can make
the gap longer than 10 microseconds. The measured gap is printed only if
the core read returns; a stall leaves the precise gap unknown.

The iPad may hang and lose USB networking. The 20-second watchdog is a
contingency, not a proven recovery mechanism for this stall. The GPC writes
and bridge-table stores have undocumented hardware effects and no automatic
rollback. Use a disposable RAM boot, with someone able to restart the iPad;
never retry after an incomplete stage in the same boot.

## Prepared inputs

The bundle `artifacts/live/gpu-test-bundle-timed-revision` is a copy of the
previous cycle bundle with `bin/gpu-core-revision-once` replaced by the new
timed executable, under the old name to reuse the pinned cycle wrapper and
watchdog supervisor. The timed bundle and original bundle are distinct.
Its manifest was checked against the files and the timed ARM64 executable was
built with `-Wall -Wextra -Werror`, statically linked.

- Timed executable SHA-256: `c76ba34ebcdd343ea3a886e1a607bd45cd58e46753fc2b47d074033ece1f49f1`
- Watchdog supervisor SHA-256: `093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f`
- Cycle core wrapper SHA-256: `55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09`

The probe checks PMGR `0x3ff` and initial GPC state zero. After the host
acknowledges the combined stage, it writes GPC offsets `0x10000`, `0`, and
`0x1000`, polls at most 64 times, checks state 1, waits at least 10 µs, and
reads `0x201000020` once. There is no host round trip after the successful
poll. The host logs and flushes each received checkpoint; the last checkpoint
before a wedged poll or revision read may be `before-gpc-poll`, so it cannot
always distinguish those two stalls. No second GPU register is read.

Mocked-MMIO tests verify write order, poll limit, unexpected-state rejection,
minimum delay, and one core read. The socket simulation checks the watchdog
and checkpoint protocol and gate failures. These do not validate real MMIO,
watchdog recovery, or an upper bound on userspace scheduling latency.

## Run sequence

Use the **cycle** boot payload, not the no-poweroff once payload. Verify and
boot `artifacts/live/gpu-pmgr-cycle/payload/m1n1-linux.bin` with SHA-256
`3dd234b5f20c85b71873a148463e5d6a682c232c1bdef9f5b5f3ea2d8ed96835`.
Follow the live-DT preflight and staging in
[full clock preparation](2026-11-07-j81-full-clock-sequence-preparation.md),
but use this bundle and stage only:

```sh
python3 boot/stage_gpu_test_bundle.py \
  --bundle artifacts/live/gpu-test-bundle-timed-revision \
  bin/gpu-pmgr-peek bin/gpu-bridge-once bin/gpu-core-revision-once \
  bin/gpu-watchdog-supervisor modules/gpu-pmgr-cycle.ko data/gfx-bridge-plan.bin \
  wrappers/gpu-pmgr-cycle-run.sh wrappers/gpu-bridge-once-cycle-run.sh \
  wrappers/gpu-core-revision-once-cycle-run.sh
```

Run the PMGR-cycle and full bridge-table captures in the linked preparation
note, in that order, and require complete success. Do **not** run its
separate GPC-init, post-GPC, or core-revision captures; this test requires
GPC state zero. Then run once, with a new log path:

```sh
python3 boot/gpu_gpc_timed_revision_capture.py \
  artifacts/live/gpu/timed-gpc-revision-$(date +%Y%m%d-%H%M%S).log \
  c76ba34ebcdd343ea3a886e1a607bd45cd58e46753fc2b47d074033ece1f49f1 \
  --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --wrapper-sha256 55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09
```

Stop on a failed preflight, nonzero return, unexpected state, timeout, reset,
or lost connection. Preserve the log and recover to a fresh boot before any
further experiment. A successful run requires the revision result and an
explicit watchdog-disarmed checkpoint.
