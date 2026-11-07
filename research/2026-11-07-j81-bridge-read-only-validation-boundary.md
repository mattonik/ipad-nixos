# J81 bridge read-only comparison boundary

Date: 2026-11-07

## Offline result

The available captures establish one extra observable after GPC initialization:
`artifacts/live/gpu/postgpc-bridge-20261106-164615.log` (SHA-256
`aa4019e566a73f5eb95f5081866d1c03c911849f6bd8469770e4aa8568c563c1`)
shows PMGR `0x3ff`, GPC state `1`, GPC control `0x40000000`, bridge
`0x201f00018 = 0x4`, and bridge `0x201f0001c = 0x10001`. The known fresh
state-0 bridge peek reads only `0x201f00018`; it says nothing about `+0x1c`.
The `+0x1c` result is therefore a candidate read-only discriminator for a
future before/after GPC-init comparison, but there is no baseline proving it
is unchanged or safe to read with GPC in state 0.

The checked-in `gpu-bridge-peek.c` requires GPC state 0 and reads only bridge
`+0x18`. The `gpu-bridge-postgpc.c` requires GPC state 1 and reads `+0x18`
and `+0x1c`; its cycle wrapper verifies active PMGR runtime usage. The
write-bearing `gpu-gpc-init.c` has checkpointed GPC accesses but no bridge
read, so no existing runner captures `+0x1c` on both sides of the transition.

## Why no extension was built

A before/after probe would need to add a read of undocumented bridge `+0x1c`
while GPC is still state 0, before the established GPC writes. A successful
read in state 1 does not prove that the same read is safe in state 0; a stalled
MMIO access could strand the same kernel execution path the existing watchdog
cannot guarantee to recover. The existing known-safe state-0 observation is
only `+0x18`. No offline source or capture establishes a register contract or
read-safe phase for `+0x1c`, so preparing a new live-capable probe would not
meet the evidence threshold. No device or firmware was used.

Safe validation available today is the state-1 post-GPC read already captured.
It confirms `+0x1c` is readable after GPC state 1, but cannot distinguish
whether GPC initialization, the PMGR cycle, or some other boot-time action
caused `0x10001`. Resolve the state-0 access contract or obtain an independently
controlled observation before expanding the probe.
