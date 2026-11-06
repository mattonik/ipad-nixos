# J81 PMGR cycle + GPC wake identity result

The new cycle payload completed the first reset-generation experiment:

```
PMGR baseline: 0x00000300
PMGR cycle:    rc=0
final lease:   runtime_status=active, runtime_usage=1
GPC init:      state 0x00000001, rc=0
```

The subsequent read-only identity probe again hung at the first RGX read,
`0x201000020`, after successful PMGR, GPC-state, and GPC-control reads. The
USB/Linux link disappeared. Capture:
`artifacts/live/gpu/gpu-id-cycle-20261106-163122.log`, SHA-256
`e786b505bbd925af18f88858599dac50562671e205ab4accf69a4320a31a71d8`.

This rules out the missing PMGR off/on generation as the sole cause of the
RGX fault. The remaining blocker is the Apple-specific RGX/Fender wrapper or
slave-port initialization (possibly bridge/clock/firmware ownership). Do not
retry the identity read in this boot; recover via normal restart/DFU.
