# J81 iPadOS fender-cpu1b0 probe (2026-11-20)

Boot C065F72D-0ED0-4C6F-8095-B7221331FAC9, archive artifacts/live/private/gpu-offline/j81-fender-cpu1b0-device.logarchive.
Same P0/P1 values as cpu20 (GPC TICKS 0x3951, Fender +0 = 0x40000000).
CORE = CPU cluster 0x202220000 +0x1b0 = 0x00000000 (DPE word, expected nonzero as positive control).

Result: third CPU-block word (+0x20, +0x48, +0x1b0) reads 0 at the end of ApplePMGR::start().
The positive control did not light up, so this read cannot distinguish "writes not done yet / block unpowered or
unpopulated at this point" from "zeros returned". It gives no state to copy to Linux.
Next candidates: +0x1a0/+0x150/+0x190/+0x194 (cheap), or move the read later in boot.
