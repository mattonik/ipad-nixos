# J81 campaign: host-paced core read

On 2026-11-09, fresh cycle-payload RAM boot
`6dca7f2a-1f44-461c-8c3a-593aa1927b72` passed the campaign preflight. The
PMGR cycle and 66 bridge-store software checkpoints completed; the bridge
watchdog disarmed. Host-paced GPC initialization returned state `1` on the
first poll, finished with `rc=0`, and disarmed its watchdog.

The separate core probe then armed the watchdog and observed PMGR `0x3ff`,
GPC state `0x1`, and GPC control `0x40000000`. The host received and
acknowledged `stage=before-gpu-revision address=0x201000020 width=32`; no
result, successful completion, or watchdog-disarmed checkpoint followed
before capture timeout. USB networking no longer responded. The operator
reported a restart. The capture does not independently establish its cause.

This reproduces test4's host-paced boundary on a new boot and makes it less
likely that the earlier combined test's result was solely a polling-speed
artifact. It does not establish the core register's value, why the access did
not return, exact timing between the GPC and revision reads, or whether the
CPU executed the load after the acknowledgement. It does not compare exact
poll-to-read intervals against the timed run; that run did not yield a timing
measurement. Do not retry on this boot.

The local raw logs are in
`artifacts/live/gpu/campaign-paced-20261109-01/`. Related results:
[GPC-only control](2026-11-09-j81-campaign-gpc-control-result.md) and
[timed test](2026-11-09-j81-campaign-timed-result.md).
