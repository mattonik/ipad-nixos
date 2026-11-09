# J81 campaign: GPC control completed

On 2026-11-09, fresh cycle-payload RAM boot
`1601e011-640f-448a-8cf0-c4f815afa0c9` passed the campaign's device-tree,
kernel-note, mount and fresh-state preflight. The PMGR cycle reported success.
The 66 bridge-table stores reached their host-acknowledged software
checkpoints and the bridge watchdog was disarmed. Those checkpoints do not
prove all stores persisted.

The host-paced GPC control read initial state zero, issued the three
previously researched setup writes, and its first poll returned `0x1`.
The probe finished with `rc=0` and its watchdog was disarmed. No GPU-core
read was attempted. This reproduces the earlier successful host-paced GPC
result, but does not reveal whether timed-v2 stalled in a poll or core read,
nor prove GPC readiness on another boot.

The private raw logs are under
`artifacts/live/gpu/campaign-control-20261109-01/`. The next comparison is
a fresh-boot timed-v3 run, which has a poll-success and a pre-core checkpoint;
its checkpoint delivery is still not guaranteed during a hardware hang. The
existing test4 capture already provides a host-paced core-read boundary.
See [campaign plan](2026-11-09-j81-gpu-test-campaign.md).
