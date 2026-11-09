# First timed GPC/revision experiment and revised probe

On 2026-11-09, boot `186df283-2e35-487d-9be9-5e38bda97cf7` used the
verified cycle payload and RAM root filesystem. PMGR cycling completed and
the 66 bridge writes reached their software checkpoints; the bridge watchdog
was disarmed. The timed probe then read PMGR `0x3ff` and initial GPC state 0,
received host authorization for the combined sequence, and emitted
`checkpoint=before-gpc-writes` and `checkpoint=before-gpc-poll`. It returned
`stage=finished rc=1` without a revision result. Its watchdog supervisor did
not disarm on this failure; network connectivity later disappeared. The logs
alone do not prove whether the watchdog caused that loss.

In the first probe's code, that result occurs if 64 immediate polls fail to
clear bit 4, the resulting low state nibble is not 1, or a clock/timer call
fails. The probe did not record the final poll value or the error, so the
particular cause cannot be recovered. The test did **not** reach a completed
GPU read and does not establish a GPU identity result. A clock call after the
poll can also fail before the core access. The former host-paced test reached
state 1 on its first poll after host checkpoints, roughly a millisecond after
the state request; this makes the new tight poll limit a plausible test
artifact, not a proven explanation.

Private captures: `artifacts/live/gpu/clock-cycle-20261109-timed-186df283.log`,
`clock-table-20261109-timed-186df283.log`, and
`timed-gpc-revision-20261109-186df283.log`.

## Revised v2

The rebuilt probe allows up to 1,000 polls with a requested 10 µs delay after
each busy result. On a bounded-poll failure it prints the last value and
count; a successful poll is still followed by a minimum 10 µs wait and one
core read without host round trips. Scheduler timing is not bounded to exact
microseconds. GPC or core MMIO can still hang, and the watchdog remains only a
recovery contingency. Failure ends the boot; never retry on that boot.

The v2 bundle is `artifacts/live/gpu-test-bundle-timed-revision-v2`. Its
probe SHA-256 is
`d67a04f7db8a5522de962daf890e801f0beb9e498e18f438ff0ea74bb95a3b4f`.
The supervisor, wrapper, PMGR module, payload and bridge-plan hashes are as
in the [first plan](2026-11-09-j81-timed-gpc-revision-test.md). Use the same
fresh cycle boot, live-DT checks, stage list, PMGR cycle and 66-write bridge
capture described there, replacing the bundle path with v2. Skip the separate
GPC and core captures. The final command is:

```sh
python3 boot/gpu_gpc_timed_revision_capture.py \
  artifacts/live/gpu/timed-gpc-revision-v2-$(date +%Y%m%d-%H%M%S).log \
  d67a04f7db8a5522de962daf890e801f0beb9e498e18f438ff0ea74bb95a3b4f \
  --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --wrapper-sha256 55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09
```

Host mocks cover immediate success, delayed success, poll exhaustion and
unexpected GPC state, and the capture socket test covers the watchdog and
host dialogue. No mock proves the MMIO or watchdog behavior on the iPad.
