# J81 guarded GFX power-on result

Date: 2026-11-06

The dedicated PMGR test payload was booted after a fresh DFU/PongoOS handoff.
The device tree contained the experimental J81 test node, and the staged
module matched the test kernel. The existing fail-stop capture then performed
one acknowledged PMGR read followed by one power request:

```
stage=before-pmgr-read address=0x20e020320 width=32
stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0
stage=before-gfx-power module=39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89 kernel_notes=82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014
stage=after-gfx-power rc=0
```

After the request, the Linux runtime-PM state was:

```
/sys/devices/gpu-pmgr-once/power/runtime_status = active
/sys/devices/gpu-pmgr-once/power/runtime_usage  = 1
```

The private raw capture is stored at
`artifacts/live/private/gpu-observations/2026-11-06-pmgr-power-test-03.log`.

## Result

- Test-node/provider validation: **pass**.
- GFX PMGR power-on request: **pass** (`rc=0`).
- Domain held active by the guarded consumer: **yes**.
- GPU/GPC MMIO, firmware upload, bridge writes, and rendering: **not
  attempted**.

This is the first confirmed hardware milestone: the J81 GFX power domain can
be acquired by the Linux PMGR path without a timeout or fail-stop error. The
next experiment is a separately bounded read-only GPU identity probe while
the domain is held active; it should not be chained automatically into this
power test.

