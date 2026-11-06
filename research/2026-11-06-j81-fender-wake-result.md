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

That read-only module is now built as
`artifacts/live/gpu-fender-status/gpu-fender-status.ko` (SHA-256
`96d29d0351529e67cbb3290f0de363ca0f15763ae03d85cf060f9d5761dbceec`, commit
`7c1032b`). It exposes `state`, `control`, and `hold` under
`/sys/devices/gpu-fender-status/`; it contains no MMIO writes and no RGX
mapping.

## Distance to rendering

The power/reset foundation is now proven, but this is not yet a renderer. The
remaining blockers are the J81 firmware/boot protocol, GPU memory/DART setup,
command submission, and a display-facing buffer path. The absent J81
`gfx-kf`/A7-IOP node means Orchard's A10 firmware transport cannot simply be
reused. The next meaningful milestone is a read-only status module plus
offline reconstruction of the A8X firmware handshake; rendering comes only
after that handshake and a controlled command-buffer test exist.

Status-read boundary: a fresh-boot status-only attempt hung at the first
Fender `state` read because the PMGR lease was not active. No write occurred;
the boot was consumed fail-closed. The status wrapper now requires
`runtime_status=active` and `runtime_usage=1` before loading the module or
touching Fender.

The guarded status capture then succeeded after a fresh PMGR cycle. Logs:
`artifacts/live/gpu/pmgr-cycle-status-20261106.log` (SHA-256
`5c1d1267b9193fd6e4b258df7cbd68f3b25d0b434f91fc5636a8fca19b374bb6`) and
`artifacts/live/gpu/fender-status-20261106b.log` (SHA-256
`e278754813a8292fdbfeac8f19900f974856d0e7f8c51fbd1e582513054fed5a`). The
read-only baseline was state `0x00000000`, control `0x00000000`, hold
`0x00000000`, `rc=0`.
