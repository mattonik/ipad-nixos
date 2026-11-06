# J81 clock/reset inventory (2026-11-05)

This is a read-only inventory from the current m1n1/Linux RAM boot. The PMGR
test module was loaded with the existing guard and reported `runtime_status=
active`, `runtime_usage=1`; the kernel and module note hashes matched the
recorded test payload. No GPU or GPC register was read or written by this
inventory.

## Device-side result

The complete capture is kept outside Git at
`artifacts/live/private/gpu-observations/clock-reset-inventory-2026-11-05.txt`.
The boot mounts only proc, sysfs, configfs, and devpts; debugfs is not mounted,
so there is no `clk_summary`, `pm_genpd_summary`, or reset-debug view to query.

The visible device nodes are:

* `/sys/devices/genpd_provider/gfx` (the Linux GFX power-domain provider),
  with only `of_node`, `driver`, and `subsystem` visible;
* `/sys/devices/gpu-pmgr-once` (the guarded diagnostic consumer);
* no Linux GPU/GFX clock device and no GPU node under the booted device tree.

The DT still contains the PMGR provider at
`/soc/power-management@20e000000/power-controller@20320`:

* `compatible = apple,t7000-pmgr-pwrstate` (the raw property is visible in the
  capture), `reg = <0x20320 0x4>`, `#power-domain-cells = <0>`, and
  `#reset-cells = <0>`;
* the J81-only `experimental,j81-gpu-test-no-poweroff` marker is present;
* the node has no `clocks`, `clock-names`, or reset consumer wiring.

The DT includes a generic seven-entry OPP table (`opp01` through `opp07`) with
`opp-hz`, `opp-level`, and latency properties. Those entries are not connected
to the GFX provider in the live tree, so they do not provide a usable Linux
clock-control path by themselves.

## Interpretation

This confirms the static conclusion in `research/2026-11-05-j81-gfx-clock-ordering.md`:
the current Linux path can hold the Apple PMGR GFX domain on, but it cannot
reproduce Apple's clock-state action. The missing piece is not a hidden sysfs
knob; it is a clock/reset provider and the Apple-specific state machine that
selects and applies the GFX clock state before the GPU is touched.

The safest next implementation step is therefore offline: model the Apple
clock-state action from the iOS traces (including its provider/GPC ordering)
behind a compile-time disabled interface, and keep hardware work limited to
read-only identification until that model has an independent timeout and
rollback proof. This inventory does not justify another bridge write or a
GPC access.

