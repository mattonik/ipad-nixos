# J81 timed GPC/revision v2: incomplete capture

On 2026-11-09, fresh cycle-payload RAM boot
`db572110-5c85-4f55-bc10-16f7cda746ac` passed the live-DT, rootfs and
kernel-note preflight. PMGR cycling completed; 66 bridge stores reached
software checkpoints and the bridge-stage watchdog was disarmed. These
checkpoints are not readback of every bridge entry.

The revised timed probe armed the 20-second watchdog, read GFX PMGR `0x3ff`
twice, and observed initial GPC state `0`. It received authorization for the
combined operation and printed `checkpoint=before-gpc-writes`, then
`checkpoint=before-gpc-poll`. Since the second checkpoint follows the three
GPC write instructions and barriers, the process progressed past those
instructions. No poll-failure value, revision result, finished checkpoint,
or watchdog-disarmed checkpoint arrived before the 35-second capture timeout.
USB networking did not respond to a subsequent ping.

The capture cannot distinguish a stalled GPC poll read from a completed poll
followed by a stalled GPU revision read, or another stall in that interval.
It does not prove that the revision address was reached, that GPC settled,
that the watchdog reset the iPad, or that the minimum-delay hypothesis has
been tested. No retry is permitted on this boot. The core observation of test4
remains separate: that older log had a checkpoint immediately before its
core access.

Private logs: `artifacts/live/gpu/clock-cycle-20261109-timedv2-db572110.log`,
`clock-table-20261109-timedv2-db572110.log`, and
`timed-gpc-revision-v2-20261109-db572110.log`. The probe and its limited
interpretation are described in
[the first result and revised plan](2026-11-09-j81-timed-gpc-revision-first-result.md).

A further test needs a way to preserve a checkpoint after a successful poll
and before the identity read without introducing the long host-mediated delay
the experiment was designed to avoid. Any such design must be validated
before another hardware round; the watchdog has not been demonstrated to
recover a wedged transaction.
