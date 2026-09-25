# J81 active-work priority

**Reviewed:** 2026-09-24 (DART and its IOMMU wiring are now both
hardware-confirmed working: the real, unmodified `apple-dart` driver
initializes cleanly, and with `pcie`'s `iommu-map` restored the IOMMU
core confirms a real translated default domain. Next is implementing the
real PCIe host-controller driver.)

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
| 1 | PCIe: implement the real host-controller driver | 5 | 2 | 5 | In progress, 2026-09-25. Stages 1-3 hardware-tested clean (write sequence, real PCI enumeration, corrected PERST handling all confirmed working). Stage 4a (`0036`) hit a real `-EBUSY` -- the per-port controller window physically overlaps `dart_apcie1`'s own MMIO region -- fixed as `0038` (non-exclusive mapping) and hardware-tested clean. **Full recovered sequence (Stages 1-4b v2) hardware-confirmed safe end to end, 2026-09-25**: the link-start write genuinely took and stuck, no crash/hang anywhere. No downstream WiFi endpoint enumerated yet after three scan attempts -- next is researching Apple's excluded cap-discovery/tunable/config-MSI steps or a link-training poll, not a blind retry. |
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
