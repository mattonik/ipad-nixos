# J81 iPadOS fender-cpu1a0 probe (2026-11-20)

Boot 1972F1F0-D87C-40F4-85C5-3B1C5322A870, archive artifacts/live/private/gpu-offline/j81-fender-cpu1a0-device.logarchive.
P0/P1 identical to cpu20/cpu1b0 (GPC TICKS 0x3905, Fender +0 = 0x40000000).
CORE = CPU cluster 0x202220000 +0x1a0 = 0x00000000.

Fourth CPU-block word (+0x20, +0x48, +0x1b0, +0x1a0) reads 0 at the hook. Two DPE words both zero: the block
reads as zeros at this point on iPadOS (unpopulated/unclocked/unmapped-as-zero, or stock writes later/conditional).
Further words (+0x150/+0x190/+0x194) are unlikely to differ; this probe family is exhausted. Waiting on the
research agent (to-builder/2026-11-20-j81-research-startup-outside-pmgr0), which asks about this block explicitly.
