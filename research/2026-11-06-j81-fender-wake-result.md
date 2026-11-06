# J81 Fender wake result

The guarded post-PMGR Fender sequence completed successfully on hardware in a
fresh diagnostic boot. The PMGR prerequisite log is
`artifacts/live/gpu/pmgr-cycle-fender-20261106e.log` (SHA-256
`5c1d1267b9193fd6e4b258df7cbd68f3b25d0b434f91fc5636a8fca19b374bb6`). The
Fender log is `artifacts/live/gpu/fender-wake-20261106c.log` (SHA-256
`9072cb2cf838aaa433c7a3fe5dc48420e3d3e3751c6f28a7560a5b9a50088b61`).

Verified readbacks:

```text
initial state       0x00000000
reset write         0x00000000
reset-clear poll    0x00000000
reset-state write   0x00000010
reset-zero poll     0x00000000
hold write          0x00000020
hold confirmation   0x00000020
setup mask          0xffff0000
setup control       0x40000000
request state       0x00000011
wake poll           0x00000000
finished            rc=0
```

This proves the J81 Fender reset/hold/wake register contract through the
known-good PMGR cycle. It does **not** prove RGX accessibility, firmware
loading, or rendering; the direct RGX identity read remains excluded because
the earlier attempt hung the device. The one-shot guard consumed this boot.

Next offline step: use this exact sequence as the foundation for a kernel-side
Fender driver, then add only a read-only status/reporting path before any
future RGX experiment.
