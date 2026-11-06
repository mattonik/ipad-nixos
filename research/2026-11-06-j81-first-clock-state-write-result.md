# J81 first clock-state bridge write result

Date: 2026-11-06

On a fresh matching PMGR test payload, the watchdog-supervised first bridge
step completed without a hang or reset:

```
PMGR read             0x000003ff (target=15, actual=15)
GPC state before      0x00000000
bridge write          0x201f00018 <- 0x80010004
watchdog              disarmed normally
```

The write is selector 9's first recovered pair. The private transcript is
stored at
`artifacts/live/private/gpu-observations/2026-11-06-gpu-bridge-first-01.log`.
The shell remained responsive after completion. No second bridge pair, GPC
control write, GPU-ID read, firmware upload, or rendering was attempted.

## Interpretation

This establishes that the first Apple clock-state bridge address is mapped and
accepts one guarded write while the Linux PMGR lease is active. It does not
show that the write changed GPC state: the only GPC observation was the
pre-write value `0`. The next experiment must therefore be a fresh boot with
an explicit post-write read checkpoint, not an automatic continuation of the
remaining 65 pairs.

