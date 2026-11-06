# J81 GPU batch run (2026-11-06)

The reusable bundle was staged over the stable dashboard USB shell into the
RAM filesystem. The running kernel notes matched the GPU PMGR test kernel:

```text
82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014
```

The batch results are in these private append-only logs:

- `artifacts/live/gpu/pmgr-once-run-20261106-final2.log`
- `artifacts/live/gpu/gpc-state-only-20261106-final.log`

Observed sequence:

```text
PMGR before:       0x00000300 (target=0, actual=0)
PMGR transition:   rc=0
PMGR after:        0x000003ff (target=15, actual=15)
GPC state:         0x00000000
```

The read-only GPC wrapper stopped at the state gate and did not read GPC
control or GPU identity registers. This reproduces the earlier boundary on a
clean staged batch and confirms the bundle/staging path works. The next
scenario (Fender wake or GPC initialization) remains a separate MMIO-write
experiment and must not be chained onto this boot.
