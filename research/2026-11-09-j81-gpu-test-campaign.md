# J81 GPU: prepared multi-boot test campaign

Prepared offline on 2026-11-09 after the incomplete timed-v2 capture. The
three modes below are alternative experiments, each requiring its own fresh
DFU → PongoOS → cycle-payload Linux RAM boot. Run one mode per boot. They
vary the timing and checkpoint placement of already investigated operations;
they do not add unverified clock, reset or MCC writes.

## Recommended order and decisions

| Boot | Mode | What it does | Interpretation |
| --- | --- | --- | --- |
| 1 | `gpc-control` | PMGR cycle; the 66 bridge stores; host-acknowledged GPC initialization and poll. No GPU-core access. | If GPC fails or hangs here, investigate that checkpoint before any core test. If it returns state 1 and watchdog disarms, the slow control completed on this boot. |
| 2 | `paced` | Same setup and host-paced GPC control, then the existing independently checkpointed revision read. | If the core read stalls after its explicit pre-read checkpoint, this reproduces the earlier boundary under this path. A returned ID is useful but does not alone identify a cause. |
| 3 | `timed` | Same setup; one process performs GPC init, paced bounded poll, emits poll-success and pre-read checkpoints, delays at least 10 µs, and reads revision once. | A received poll-success/pre-read checkpoint followed by no result narrows the boundary to after those checkpoints. If they never arrive, the poll, checkpoint delivery, timing or later system behavior remain ambiguous. A returned ID includes measured poll-to-read elapsed time. |

A completed GPC-only run need not be followed by a core read on that same
boot: keeping runs separate preserves the comparison. If a test hangs, fails,
loses USB, or has an unexpected state, stop and recover with a fresh boot;
do not automatically advance to the next test. Earlier test4 already provides
one host-paced core-stall observation, so `paced` can be skipped if the
operator wishes to prioritize the updated timed run after the GPC control.

## What is prepared

`boot/gpu_campaign.py` validates the exact bundle hashes, checks the live DT,
kernel notes, RAM-only mounts and absent prior test markers, records the boot
ID and preflight output, stages the selected inputs, then runs each existing
host capture in order. Its preflight is read-only. Each capture writes an
exclusive log in a new per-run directory; any nonzero step stops the runner.
The target retains the existing one-shot guards and watchdog supervisor.
The runner does not manage DFU, reboot the iPad or automatically start
another boot. Its failure message cannot guarantee the target is recoverable.

The timed executable writes its two new checkpoints to the supervisor pipe
without a host acknowledgement. Pipe writes and scheduling can add delay;
this is not an exact 10-µs measurement. The clock interval is printed only
if the core read returns. A system-wide stall can prevent a checkpoint from
reaching the Mac, so its absence is not proof of where execution stopped.
The host writes and fsyncs received capture bytes, but cannot recover bytes
that never arrived. The 20-second watchdog remains a contingency, not a
proven recovery mechanism for an interconnect stall.

The local v3 bundle is
`artifacts/live/gpu-test-bundle-timed-revision-v3`; timed executable SHA-256
`a489491f0dc9e285f9fb6adcdc3b05d2fcf7f86921fa53464cbefba0781728ea`.
The `paced` mode uses the earlier separately pinned
`artifacts/live/gpu-test-bundle-20261107-core-revision`. Bundle binaries and
raw hardware logs are local artifacts, not part of a clean Git checkout.

## Operator sequence

For each mode, start the verified cycle payload described in
[full clock preparation](2026-11-07-j81-full-clock-sequence-preparation.md).
Once the Linux RAM dashboard and USB networking are up, from the repository
root run **one** command, giving a new directory each time:

```sh
python3 boot/gpu_campaign.py gpc-control artifacts/live/gpu/campaign-control-01
python3 boot/gpu_campaign.py paced artifacts/live/gpu/campaign-paced-01
python3 boot/gpu_campaign.py timed artifacts/live/gpu/campaign-timed-01
```

These lines are three separate DFU cycles, not a batch to paste into one
shell. Review the first run and reboot before choosing the next. The runner
verifies the mode's bundle before touching the target; a checksum mismatch,
missing file, wrong kernel, wrong DT property, unexpected mount, previously
inserted cycle module or existing one-shot marker stops before test execution.
Check the per-run `preflight.log`, runner logs and raw capture logs after
failure; no missing checkpoint can be assumed to mean that a hardware access
did not occur.

Host-only checks exercise campaign mode selection and stop-on-failure,
checkpoint delivery in a simulated core stall, the paced-poll MMIO mock, and
bundle digests. They do not demonstrate real GPU behavior, checkpoint
delivery through a hardware hang, or watchdog reset reliability. No hardware
was accessed while preparing this campaign.
