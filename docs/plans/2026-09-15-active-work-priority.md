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
| 1 | CHG-2: map charger cable/status behavior with a USB meter | 5 | 4 | 5 | CHG-1 passed on J81 on 2026-09-21; record disconnected, data-host and known-charger cases without PMIC writes. |
| 2 | Repeat ANS1's intentionally read-only hardware observation | 4 | 4 | 3 | Requires the separate observation-only payload; never mount or write it. |
| 3 | Passively trace the D2207 I2C bus during an iPadOS Bluetooth transition | 4 | 2 | 5 | Requires a logic analyser and iPadOS; no injected transactions. |
| 4 | Touch: resolve firmware/calibration delivery and power ownership | 3 | 2 | 5 | Blocked by the non-persistent D2207 LDO/GPIO state and private touch data. |
| 5 | T7000 PCIe host: finish one per-port register class and enable order | 3 | 2 | 5 | ECAM, shared, controller and pair-PHY classes are mapped; disabled DT/DART topology and compile-only skeleton are ready; do not access registers yet. |
| 6 | Charging policy writes | 2 | 1 | 5 | Blocked by cable/meter observations and PMIC runtime ownership. |
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
charger child.  Hardware registration and raw-register decoding were then
verified on J81 on 2026-09-21; charging behavior remains unproven.

## Completed CHG-1 hardware check (2026-09-21)

The live observer reported `100000` uA and `3000000` uA.  Raw registers
`0x04c0 = 0x02` and `0x04cf = 0x3c` decoded to those same values, satisfying
the CHG-1 acceptance gate.  The battery was present but reported
`Discharging` at about `-645000` uA.  The action used only PMIC
address-select-plus-read transfers.

## Next action, with a USB power meter

Record disconnected, data-host and known-charger cases: meter voltage/current,
gauge current, `0x04c0`, and the read-only D2207 status block.  Those cases
are needed to name status bits and explain the 100 mA data-host limit before
any charging-control design is considered.

## Completed button check (2026-09-21)

`evtest /dev/input/event0` captured press and release events from Home
(`KEY_HOMEPAGE`), Power, Volume Up and Volume Down.  The existing
`gpio-keys` device therefore has complete hardware coverage; no new payload
or driver is required for buttons.

## Explicitly deferred

Do not add a D2207 GPIO/regulator/charging write path, attempt PCIe link
training, enable a touch child, make ANS1 writable, or begin GPU/audio work
from this ranking alone.  Each is below a missing evidence or hardware gate
listed above.
