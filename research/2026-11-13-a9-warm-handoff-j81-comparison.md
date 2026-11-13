# A9 warm-handoff work: implications for J81

Offline source review on 2026-11-13. Orchard's [PR 107][pr107] head
`57e91ab3b84a2977877ea843372f3428fab51234` and [PR 125][pr125] head
`c57f87b78a0754ae63847b26834ea98826009ad8` were examined. They describe
Linux-to-Linux kexec and m1n1 re-entry on A9/J71t, not an iPadOS-to-Linux
transition on A8X. PR 107 is draft; both are part of a stacked series. No J81
hardware action was performed.

## What the code does and what transfers

| Area | A9 implementation and evidence | J81 implication |
| --- | --- | --- |
| Retained-state signal | m1n1 adds `/chosen/linux,booted-from-kexec` on PSCI re-entry; the PMGR patch checks this marker **and** the `apple,s8000-pmgr-pwrstate` compatible. | Our ordinary J81 boot is neither the demonstrated A9 transition nor S8000. Do not spoof the marker or assume it activates this code for T7001. A J81 transition would need an explicit, verified provenance contract. |
| Domain hold | On a marked A9 warm boot the PMGR patch blocks power-off and clock disable and suppresses auto-PM for held domains. The later series keeps the hold for the **whole boot**: releasing it at `sync_state` was followed by SoC locks. | Identify and hold inherited J81 dependencies *before* Linux can gate them. Our late manual restore did not establish uninterrupted retention. The A9 observation is a reason to investigate, not evidence that a hold fixes J81. Broad holds have power and sleep costs. |
| PMGR writes | Warm probe can actively request state 15 for domains already observed active, and waits for actual state; write errors/timeouts are returned. | This is not a passive preservation mechanism. Audit every early write and sample before and after it; a request can alter the state under study. |
| Logging | The A9 series reserves a 2 MiB ramoops area early in Linux memory setup, carries its FDT reservation into kexec, and avoids consuming the original records in a capture kernel. | Useful for a later Linux-to-Linux failure; it does not capture XNU or a failure before the first Linux kernel has reserved and written it. A cross-OS buffer needs independently verified ownership, cache handling and survival. |
| Teardown | G5P closes admission, bounds IRQ/drain waits and requests pstore plus emergency cold restart on a failed handover instead of knowingly jumping with live DMA. | Treat DMA quiescence, bounded waits and durable pre-transition markers as prerequisites. An A9 G5P firmware teardown is not a G4G/XNU teardown, and a reset does not guarantee filesystem integrity. |

The A9 PR reports more than 20 Linux warm restarts on J71t, including
restarts after GPU work; the cold-reset failure escape and power-on race fix
were not demonstrated on hardware in its stated testing. Neither result
validates the mechanism on J81.

## Concrete next checks

1. **Host-only boot-path audit:** trace our exact Pongo/m1n1 payload and Linux
   T7001 PMGR probe, sync-state and unused-domain handling. List every write
   that can occur before the first proposed checkpoint, including DWI/GFX and
   auto-PM. Compare actual DT compatibles, build configuration and markers;
   do not infer retention from `pd_ignore_unused` alone.
2. **Retention-control design:** on an ordinary Linux RAM boot, first verify
   whether early, read-only snapshots and a deliberately selected domain
   hold can be observed without a transition. Compare a control boot against
   the held boot at the same points. DWI and GFX status are observations, not
   proof of correct rail voltage, firmware state, GPU readiness or safe DMA.
   Such a hold changes hardware policy and needs its own reviewed test and
   recovery plan; it is not run by this review.
3. **Handoff-independent staging control:** as in the [existing feasibility
   plan](2026-11-12-j81-warm-handoff-feasibility.md), establish a bounded,
   owned Pongo-to-XNU buffer and verify its contents at two XNU checkpoints
   while returning normally. This does not prove a transition or persistence
   across reboot. Only after ownership is proven should a cross-OS log design
   or larger image be considered.
4. **Do not jump yet:** define the XNU stop/CPU/interrupt/DMA/filesystem and
   Linux entry contracts, how GPU state is checked before and after transfer,
   and an independently observable failure path. A hard reset can recover a
   hung device while still leaving corrupted data.

[pr107]: https://github.com/OrchardLinux/orchard/pull/107
[pr125]: https://github.com/OrchardLinux/orchard/pull/125
