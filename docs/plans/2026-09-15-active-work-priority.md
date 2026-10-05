# J81 active-work priority

**Reviewed:** 2026-10-04 (authoritative current state:
`research/2026-10-04-session-handoff.md`). The D2207 GPIO map is corrected
(Bluetooth GPIO2 = `0x0402`, Wi-Fi `REG_ON` GPIO3 = `0x0403`); the in-kernel
`REG_ON` assert makes the BCM4350 enumerate on hardware; touch has power-up/IRQ
and repeatable clocked RX evidence but no valid protocol ACK. The 2026-09-26
review text that gated PCIe on a "runtime owner/interlock" is withdrawn.

This is the live backlog distilled from `docs/project-status.md`, the
subsystem plans, and the driver-gap research. It excludes completed
boot/USB investigations and intentionally deferred historical experiments.

Scores are 1-5: higher certainty means stronger J81 evidence; higher ease
means less new code and lower risk; higher impact means a clearer
improvement to a usable Linux tablet. Hardware-only observations are
included because they can close a blocker cheaply, but they are never
substituted with guessed software writes.

| Order | Work item | Certainty | Ease | Impact | Current gate |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | PCIe: BCM4350 power control and link | 5 | 4 | 5 | **Hardware-confirmed 2026-10-04:** the in-kernel `REG_ON` assert (`0x0403` -> `0x0b`, patch `0050`) makes the BCM4350 enumerate (`14e4:43a3`, rev `0x05`, 2.5 GT/s x1, DLLLA set). PCIe warnings are benign. Next: Bluetooth `0x0402` (separate approval), firmware/NVRAM selection (private-capture gated), production link-wait on DLLLA. See `research/2026-10-04-session-handoff.md`. **Queued next task (after the pending hardware tests): replace the `+0x88` bit-6 link poll with DLLLA, see the handoff.** |
| 2 | Charging Stage 2: writable `input_current_limit` kernel property | 5 | 5 | 3 | **Done 2026-10-04:** sysfs write = raw register at 500/1000/2400 mA. Boot-time policy (`m1n1-hoolock-tablet`): agreed policy is 2400 mA below 80% and 42 C, 500 mA at or above either limit or if either reading is unavailable. The booted revision covers the temperature part; the 80% cap is an uncommitted working-tree change, not yet booted. |
| 3 | Repeat ANS1's intentionally read-only hardware observation | 4 | 4 | 3 | Requires the separate observation-only payload; never mount or write it. |
| 4 | Touch: power-up/IRQ and clocked RX proven; no valid ACK yet | 4 | 3 | 5 | **2026-10-04:** Apple's power order, clock, polarities and SPI bus produce the boot interrupt and a repeatable clocked RX pattern (`f8 80`, shifted one bit in mode 2), independent of the bytes sent and not a recovered ACK; command reception is unproven. Download mode is optional/non-gating and the `display_sync` pinmux (GPIO55 function 1) was tried on hardware 2026-10-05 with no change in the ROM's response; the remaining step is the firmware decision, a separate explicit user decision. See `research/2026-10-04-session-handoff.md`. |
| 5 | ~~Passively trace the D2207 I2C bus during an iPadOS Bluetooth transition~~ superseded | 4 | 2 | 1 | **Superseded 2026-10-04:** the non-persistent GPIO2 writes targeted the wrong register (GPIO2 = `0x0402`, GPIO3 REG_ON = `0x0403`), so no logic-analyser capture is required. Bluetooth GPIO2 `0x0402` stays untouched until a separate, user-approved step. |
| 6 | Suspend-to-idle audit | 2 | 2 | 4 | Needs driver power ownership after touch/PCIe work; deep suspend remains later. |
| 7 | Audio playback | 2 | 1 | 4 | Needs old-Apple I2S/DMA, codec and routing work. |
| 8 | Native GPU / KMS | 1 | 1 | 5 | Needs exact BVNC, DART/power/firmware and a new A8X platform port. |
| 9 | Writable internal storage | 1 | 1 | 3 | Explicitly blocked: preserve the proven read-only ANS1 configuration. |
| 10 | Sensors, cameras, Touch ID and NFC | 1 | 1 | 1 | Missing M8/ISP/SEP/proprietary protocols; defer. |

## Completed since the 2026-09-15 version

- **CHG-1 and CHG-2 (charging): fully resolved, 2026-09-21.** Real
  `Charging` status achieved and understood end to end -- `0x04c0`
  (input current limit) is the real, AP-writable register; `0x0010` bit 2
  is Apple's own named `setCurrentLimitSuspend` control, not a mystery bit.
  All five tiers (100/500/1000/2100/2400 mA) validated live on real
  hardware, all clean (no voltage droop, no thermal concern, no USB link
  instability at any tier). A console tool (`Charging: switch current
  tier`) makes this reproducible without raw `i2ctransfer` syntax. Device
  is currently running at 2400 mA under a recurring safety monitor
  (80% capacity / 42 C auto-cutoff). Full record in
  `docs/plans/2026-09-13-pmic-pcie-execution.md`.
- **Buttons: verified complete, 2026-09-21.** All four physical inputs
  (Home, Power, Volume Up/Down) produce clean Linux events on the existing
  `gpio-keys` device. No further work needed.
- **PCIe: enable-order evidence gap closed, 2026-09-21.** The exact
  `AppleT7000PCIe`/`AppleEmbeddedPCIEPort` port-enable sequence is now
  fully recovered from the real iOS 8.1 kernelcache -- register offsets,
  bit positions, and confirmed (not inferred) microsecond-precision
  delays. The previously-open second per-port register-window class
  (entries 2/4/6/8) is confirmed unused by Apple's own host path -- closed
  as a real negative result, not left open. CLKREQ confirmed
  endpoint/controller-managed, not host-toggled. All static analysis; no
  J81 controller register was read or written. Full record in
  `docs/plans/2026-09-13-j81-wifi-pcie.md`.

## Explicitly deferred

Do not add a D2207 GPIO/regulator write path beyond the already-validated
charging registers, attempt PCIe link training or hardware bring-up before
the isolated payload is cross-build verified, enable a touch child, make
ANS1 writable, or begin GPU/audio work from this ranking alone. Each is
below a missing evidence or hardware gate listed above.
