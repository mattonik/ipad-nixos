# Orchard bit-30 comparison and the next J81 observation

Offline comparison of Orchard's draft G5P transport, the local iPadOS 15
AGX code, and the J81 test captures. No device access.

## The same-looking constant has different meanings

The iOS 15 T7000 map routine writes `0x40000000` (bit 30) into two mapped
GPU-window registers at offsets `+0x1008` and `+0x4008`, preserving the lower
30 bits. Those are accesses through the driver's mapped GPU window, not the
J81 Fender register at `0x201e00000 + 0`. The J81 pre-ID path writes
`0x40000000` to Fender `+0`, where it is the documented setup-control word.
The numeric coincidence is not evidence that the iOS 15 `+0x1008/+0x4008`
operations belong in the J81 sequence.

Orchard's G5P draft adds a third, separate use: its later recovery code reads
bit 30 of `R1+0` only after a verified stop leg and before retirement. That is
a post-transport stability check, not a power-on prerequisite. Orchard also
writes `0x40000000` to Fender `R1+0` during its own G5P wake sequence, but the
G5P transport, page size, and firmware contract are not J81-compatible.

## What is now testable

The safe next observation is a paired snapshot, not another wake or RGX read:

1. the existing `gpu-fender-status` read-only module records J81 Fender state,
   control, and hold; and
2. the existing `gpu-pmgr-perf-peek` reads the PMGR GFX table/control and power
   state.

`boot/gpu_bit30_report.py` combines those logs and reports Fender control bit
30 alongside PMGR perf-control bit 31. It performs no MMIO and prints
`writes=none`. A result where Fender bit 30 is set while PMGR bit 31 is clear
would separate the two control domains; the inverse would show that only the
LLB perf-control bit is present. Either result is useful before attempting any
new write.

This is an observation artifact only. It does not claim that either bit gates
the stalled RGX identity read, and it does not alter the existing test order.
