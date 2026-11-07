# J81 live GPU experiment: test2 result

Date: 2026-11-07

## Outcome

The PMGR cycle completed successfully (`rc=0`; initial PMGR raw value
`0x00000300`) in `artifacts/live/gpu/clock-cycle-20261107-test2.log`. The
following supervised selector 9/10 clock-table phase completed (`rc=0`) with
66 bridge-table writes checkpointed in
`artifacts/live/gpu/clock-table-20261107-test2.log`. The subsequent GPC-init
phase completed (`rc=0`): initial GPC state was 0 and its poll returned state
1 in `artifacts/live/gpu/gpc-init-20261107-test2.log`.

The first post-GPC host parser attempt failed before sending `ARM`. A retry in
the same boot sent `ARM`, but the capture rejected the echoed `ARM` response.
The log,
`artifacts/live/gpu/postgpc-bridge-20261107-test2.log`, contains the command
preamble and no armed or post-arm checkpoints, and no bridge register results.
USB networking subsequently stopped responding, so the device state is
unknown. Neither attempt establishes that either bridge register was read.

## Evidence boundary and disposition

No post-GPC values for bridge `+0x18` or `+0x1c` were established by test2.
Do not reuse the historical values (`0x4`, `0x10001`) as this run's results.
Given the incomplete capture and unknown device state, do not make further
attempts in this boot; re-establish a fresh verified RAM boot before any
separately authorized experiment. This result does not establish GPU firmware
execution, job submission, or rendering.

The four logs above are the direct evidence. The run sequence and watchdog
limits are described in [the full clock-sequence preparation](2026-11-07-j81-full-clock-sequence-preparation.md);
the earlier runbook's firmware and stage-4 gates remain in force
([morning runbook](2026-11-06-j81-gpu-morning-runbook.md)).
