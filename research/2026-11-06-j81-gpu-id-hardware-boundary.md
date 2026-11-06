# J81 GPU ID hardware boundary (2026-11-06)

The dedicated PMGR test payload booted through the normal m1n1 path and kept the
dashboard/USB shell alive. The PMGR gate accepted one guarded GFX power request:

- PMGR read: `0x20e020320 = 0x000003ff` (`target=15`, `actual=15`, `auto=0`, `reset=0`)
- power request: completed with `rc=0`

The follow-up one-shot GPU ID reader then stopped before any control or GPU-core
read because the first GPC state register returned:

```text
0x201e01000 = 0x00000000
```

The safety contract requires `(state & 0x1f) == 1`; therefore the reader did
not access `0x201e00000`, `0x201000020`, or `0x201000018`. The device remained
responsive and the USB dashboard link stayed up.

This separates the remaining problem from USB, payload selection, and PMGR
ownership: the A8X GPC core is not in the settled state expected by the
read-only ID sequence after the single PMGR transition. Do not retry the ID
reader in this boot. The next offline task is to compare this state contract
with the iOS 8.1/iPadOS 15 GPC bring-up order and add only a read-only,
checkpointed observation of the prerequisite clock/reset state.
