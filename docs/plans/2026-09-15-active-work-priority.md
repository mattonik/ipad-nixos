# J81 active-work priority

**Reviewed:** 2026-09-15

This is the live backlog distilled from `docs/project-status.md`, the
subsystem plans, and the driver-gap research.  It excludes completed boot/USB
investigations and intentionally deferred historical experiments.

Scores are 1–5: higher certainty means stronger J81 evidence; higher ease
means less new code and lower risk; higher impact means a clearer improvement
to a usable Linux tablet.  Hardware-only observations are included because
they can close a blocker cheaply, but they are never substituted with guessed
software writes.

| Order | Work item | Certainty | Ease | Impact | Current gate |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | CHG-1: validate read-only D2207 charging reporting | 5 | 5 | 4 | Requires a normal control-payload boot and the existing USB connection; no PMIC writes. |
| 2 | Verify Home, Power and volume input events | 5 | 5 | 2 | Requires a live USB shell only. |
| 3 | Repeat ANS1's intentionally read-only hardware observation | 4 | 4 | 3 | Requires the separate observation-only payload; never mount or write it. |
| 4 | Passively trace the D2207 I2C bus during an iPadOS Bluetooth transition | 4 | 2 | 5 | Requires a logic analyser and iPadOS; no injected transactions. |
| 5 | Touch: resolve firmware/calibration delivery and power ownership | 3 | 2 | 5 | Blocked by the non-persistent D2207 LDO/GPIO state and private touch data. |
| 6 | T7000 PCIe host: finish controller-window roles and link sequence | 3 | 2 | 5 | ECAM and shared-block classes are mapped; disabled DT/DART topology and compile-only skeleton are ready; do not access registers yet. |
| 7 | Charging policy writes | 2 | 1 | 5 | Blocked by cable/meter observations and PMIC runtime ownership. |
| 8 | Suspend-to-idle audit | 2 | 2 | 4 | Needs driver power ownership after touch/PCIe work; deep suspend remains later. |
| 9 | Audio playback | 2 | 1 | 4 | Needs old-Apple I2S/DMA, codec and routing work. |
| 10 | Native GPU / KMS | 1 | 1 | 5 | Needs exact BVNC, DART/power/firmware and a new A8X platform port. |
| 11 | Writable internal storage | 1 | 1 | 3 | Explicitly blocked: preserve the proven read-only ANS1 configuration. |
| 12 | Sensors, cameras, Touch ID and NFC | 1 | 1 | 1 | Missing M8/ISP/SEP/proprietary protocols; defer. |

## Completed first item: current payload build

The current `m1n1-hoolock-control` payload was rebuilt on the restored Linux
builder with:

```sh
nix build .#packages.x86_64-linux.m1n1-hoolock-control --no-link -L
```

It completed successfully and produced
`/nix/store/76saw65fjsiv1clj4bvvfl5ka4k7fsdx-ipad-air2-m1n1-hoolock-control`.
This validates the current normal payload, including the read-only D2207
charger child.  It does not claim hardware registration or charging behavior.

## Next action, when the iPad is booted

Run `boot/ipad_console.py` and choose **Charging: read-only D2207 snapshot**.
It compares the driver's sysfs values with raw registers `0x04c0` and
`0x04cf`.  A match is the acceptance gate for CHG-1; record that result before
using a USB meter across the cable cases.  The action only performs PMIC
address-select-plus-read transfers and cannot write a PMIC register.

## Explicitly deferred

Do not add a D2207 GPIO/regulator/charging write path, attempt PCIe link
training, enable a touch child, make ANS1 writable, or begin GPU/audio work
from this ranking alone.  Each is below a missing evidence or hardware gate
listed above.
