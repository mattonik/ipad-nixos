# J81 campaign: timed GPC/core attempt

On 2026-11-09, cycle-payload RAM boot
`ac894e4b-7cfc-4708-9026-66958bc16121` passed the campaign preflight. The
PMGR cycle and all 66 bridge software checkpoints completed; the bridge
watchdog was disarmed. Bridge checkpoints are not readback of all stores.

The timed probe armed its watchdog, observed PMGR `0x3ff` and initial GPC
state `0`, and issued the three GPC setup writes. Its host log received:

```
checkpoint=before-gpc-poll
checkpoint=gpc-poll-ok raw=0x00000001 polls=5
checkpoint=before-gpu-revision
```

No revision result, elapsed-time measurement, successful completion or
watchdog-disarmed checkpoint arrived before the capture timeout. A subsequent
USB-network ping failed. The logged poll checkpoint establishes that this
run's GPC poll returned `1` after five reads and the probe emitted the
pre-revision checkpoint; it narrows the prior timed-v2 ambiguity.

The pre-revision checkpoint is followed by a `nanosleep` and
`clock_gettime` before the core MMIO read. Consequently it does **not**
prove the read at `0x201000020` was issued, nor can it identify the stall as
the GPU access or establish the actual poll-to-read interval. The prior
host-paced test4 has a separate acknowledged checkpoint immediately before
its core access and also did not return. These observations do not prove
why the GPU is unreachable or whether a watchdog reset occurred.

Logs are in the private local directory
`artifacts/live/gpu/campaign-timed-20261109-01/`. Do not retry on this boot.
The preceding [GPC-only control](2026-11-09-j81-campaign-gpc-control-result.md)
finished and disarmed its watchdog. See the
[campaign plan](2026-11-09-j81-gpu-test-campaign.md) for conditions and
interpretation.
