# J81 active-work priority

**Reviewed:** 2026-09-26 (a vtable address-point correction invalidates the
old interpretation of Stage 5H: it replayed a disable-side hook, not an
enable-side prerequisite. More importantly, J81's BCM4350 `WLAN_REG_ON` is
low in the live Stage 5H session, while Apple's PCIe path asserts it and waits
100 ms before starting the port. The immediate work is to recover a safe,
evidence-backed REG_ON control path, then test that prerequisite alone.)

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
| 1 | PCIe: assert the BCM4350 power prerequisite | 5 | 2 | 5 | The host path, DART and IOMMU are hardware-clean, but no endpoint enumerates because `WLAN_REG_ON` (D2207 GPIO3) is low in the live Stage 5H session. Apple asserts it, waits 100 ms, then enables the PCIe port. The recovered configure path also has an unported PHY-pair sequence. Correct the historic vtable mapping before relying on Stage 5G/5H; first recover and validate persistent REG_ON control, then test that one prerequisite with the Apple delay. |
| 2 | Charging Stage 2: writable `input_current_limit` kernel property | 5 | 4 | 3 | Implemented and cross-build verified clean, 2026-09-25 (`kernel/patches/0017-...`, isolated `m1n1-hoolock-charging-writable-test` payload, mirroring the ANS1-test pattern). First attempt hit the Linux-builder VM's disk being full from five back-to-back builds; a retry after idle time succeeded (see `docs/build-infrastructure.md`). Not yet hardware-tested. |
| 3 | Repeat ANS1's intentionally read-only hardware observation | 4 | 4 | 3 | Requires the separate observation-only payload; never mount or write it. |
| 4 | Touch: resolve firmware/calibration delivery and power ownership | 3 | 2 | 5 | Blocked by the non-persistent D2207 LDO/GPIO state and private touch data. |
| 5 | Passively trace the D2207 I2C bus during an iPadOS Bluetooth transition | 4 | 2 | 4 | Requires a logic analyser and iPadOS; no injected transactions. The `0x0010` master-enable hypothesis was tested and ruled out 2026-09-21, narrowing but not closing this. |
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
