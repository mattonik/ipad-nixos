# J81 GPC with early DWI hold: result

On 2026-11-13 the [prepared comparison](2026-11-13-j81-dwi-hold-gpc-test.md)
ran once on the existing early-DWI-hold RAM boot. The preflight verified the
hold boot and kernel identity; it was the same boot as the earlier hold
observation. The PMGR cycle returned success, all 66 checkpointed bridge
writes completed, and the bridge watchdog disarmed. The GPC batch reported
state 1 after 11 polls, then completed and disarmed its watchdog. The iPad
responded to ping afterward.

| Observation | Before cycle | Before bridge | Before GPC | After GPC |
| --- | ---: | ---: | ---: | ---: |
| DWI `0x20e020120` | `0xff` | `0xff` | `0xff` | `0xff` |
| PMGR `0x20e02300c` | `0` | `0` | `0` | `0x164` |
| Page 5 `0x20e005004` | `0` | `0` | `0` | `0` |

In the GPC batch, the state-1 poll occurred after the state request; the
reported store-to-poll interval was bracketed at more than 292,958 ns and
less than 294,792 ns. The immediate page-5 read was `0`, loaded less than
1,000 ns after the successful poll load; the later read was `0`, loaded less
than 102,000 ns after that poll load. Both samples had bit 30 clear.

This shows that **early DWI hold, with DWI on at these sampled boundaries,
did not make the Linux post-GPC page-5 value match the earlier iPadOS
`0x40000000` observation**. The PMGR `0x2300c` transition matches the earlier
late-DWI-on comparison, but does not identify its physical rail or prove a
voltage. The hold blocks a Linux callback, not hardware automatic gating or
other writers; the samples do not prove continuous state. Other boot state,
clocks, resets, software/firmware activity or a short earlier page-5 pulse
remain untested. This result does not establish why core access stalls or
justify inferring a working GPU.

No PMU access, GPU-core read or page-5 write was made by this campaign. The
raw, checkpointed logs are private at
`artifacts/live/private/j81-dwi-gpc-run-20261113-01/`. The GPU setup and DWI
hold remain in effect on this boot; the one-shot guards prohibit rerunning the
campaign without a fresh boot.
