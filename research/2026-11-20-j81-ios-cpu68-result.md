# J81 iPadOS fender-cpu68 probe (2026-11-20)

Boot DFCDA444-4E72-4056-B99B-BF0E17E7F31E, archive artifacts/live/private/gpu-offline/j81-fender-cpu68-device.logarchive.
P0/P1 as in earlier runs (GPC TICKS 0x3954, Fender +0 = 0x40000000).
CORE = CPU cluster 0x202220000 +0x68 low word = 0x00000000.

The agent's best control (+0x68, low 0x00080000 expected from LLB, preserved by kernel) also reads 0 (32-bit read).
Five CPU-block words now zero at the hook: +0x20, +0x48, +0x68, +0x1a0, +0x1b0. The block is inert/zero-returning at this
phase with 32-bit reads (or 64-bit width matters, or it is unclocked). It carries no state to copy to Linux.
CPU-block probes are exhausted. Remaining ideas: 64-bit read (needs new module), later-phase read, Linux timing,
the unmodelled provider slots +0x568/+0x570 before the stock core read.
