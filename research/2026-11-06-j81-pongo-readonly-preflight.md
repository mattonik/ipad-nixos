# J81 PongoOS read-only preflight

Date: 2026-11-06

The iPad was connected in a fresh PongoOS session (`05ac:4141`, PongoOS
2.6.3). A host-side control-transfer capture of `dt` completed without
writing device state or touching the GPU. The private capture is stored under
`artifacts/live/private/gpu-observations/` and is Git-ignored.

Observed identity in the capture:

```
target-type           J81
platform-name         t7001
regulatory-model      A1566
```

Capture SHA-256: `e77f4e7c4ba8330da763ef0992574f14b630ea6d7050db6090b190c9c98f2b45`

The capture is 163,843 bytes. It contains the PMGR device and its `GFX`
performance-domain label, but no direct GPU MMIO node/name was emitted by
this PongoOS `dt` view. This is consistent with the existing plan: the
Pongo-only preflight proves transport and target identity, while the next
stage requires the already-built Linux diagnostic payload to expose the
read-only PMGR/runtime-state observer. No PMGR writes, GPU bridge access,
GPC initialization, firmware upload, reboot, or rendering was attempted.

## Result

- Stage-3 transport/identity preflight: **pass**.
- Linux read-only PMGR/GPU observer: **not run** (PongoOS has no Linux sysfs
  observer and loading a new payload was outside this unattended safe check).
- Device left in the same fresh PongoOS state.

