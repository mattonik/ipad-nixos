# J81 touch callback resolution: download mode and display sync

Date: 2026-10-04. Static analysis only. No live-device command or hardware
write was made for this note. Evidence labels: **E** directly observed in the
listed binary, ADT or prior capture; **I** an inference; **U** unresolved.

## Result

Neither unresolved callback is a reason to add a guessed GPIO or to repeat the
previous SPI probe.

### `function-enable_download`

- **E:** J81's captured multi-touch ADT text does not contain
  `function-enable_download`.
- **E:** The public J82 iOS 10.3 personality also has no such property; it
  matches `multi-touch,j82` and supplies the normal J82 timing/calibration
  properties.
- **E:** In the matching public unstripped `AppleMultitouchSPI` binary,
  `AppleMultitouchZ2SPI::downloadModeSetEnabled(bool)` looks up precisely
  `function-enable_download`. If the provider cannot supply it, the method
  returns `0xe00002c7` (`kIOReturnUnsupported`) without issuing a GPIO or SPI
  operation. If present, it passes the requested boolean as the first callback
  argument and no mode argument.
- **E:** The same public J82 implementation's `finishStarting()` calls the
  instance-vtable download-mode slot with `true`, then immediately continues
  to the next startup call without branching on its return value. Its
  `downloadModeSetEnabled(true)` result therefore cannot gate that boot path:
  a missing callback produces `kIOReturnUnsupported`, which is ignored.
- **I:** Absence is therefore normal for at least one J82 configuration, not
  evidence for an undocumented J81 GPIO. Do **not** invent a Linux
  `download-gpios` resource or fake a success result.
- **U:** The workspace does not contain an iOS 8 J81 kernelcache/kext from
  which to reproduce that exact version's vtable trace. The saved iOS 8
  reconstruction records an enable-before-reset-release / disable-afterward
  sequence, but not a return-value branch. The directly inspected J82 sibling
  establishes the practical conclusion—unsupported download mode is
  non-fatal—not an exact-binary claim about iOS 8.

### `function-display_sync`

- **E:** The same driver implements enable by calling its Apple GPIO function
  with `value = NULL`, `readback = NULL`, and a third argument of `3`; disable
  passes all three arguments as `NULL`.
- **E:** J81's `OIPG` descriptor for GPIO55 is flags `01 01 00 02`. The Apple
  GPIO provider maps callback mode `3` to descriptor byte `f3`, hence to pin
  mode `2`. That setter selects peripheral function 1 (`PERIPH = 1`, input
  enabled); because enable supplies no value, it does not set a logical level.
- **E:** The initial and latest read-only J81 snapshots report GPIO55 as
  `0x00072a82`: `PERIPH = 0`, plain GPIO output low. It is therefore *not*
  already in Apple's requested state. GPIO51's recorded `PERIPH = 1` provides
  an independent field-decode cross-check on the known SPI3 chip-select.
- **I:** The omitted action is a reversible pin-function selection, not a
  GPIO-high write. Whether the display pipeline drives a useful waveform there
  under Linux's inherited simple framebuffer remains unknown. See
  [`2026-10-04-display-sync-pinmux-decode.md`](2026-10-04-display-sync-pinmux-decode.md).
- **U:** The electrical purpose of this mode and whether firmware operation
  needs a display-generated waveform remain unknown. It must not be represented
  as a static GPIO-high enable in a Linux driver.

## Consequences for implementation

1. Do not add a made-up download-mode GPIO or an explicit GPIO55 high write.
   GPIO55 peripheral-function selection is a separate, reversible hardware
   experiment and still requires explicit approval.
2. Keep the current touch diagnostic's result scoped correctly: power, reset,
   clock and boot IRQ are proven; command acceptance and firmware transport are
   not.
3. Treat `function-enable_download` as optional and non-gating; do not add a
   hardware action for it. An exact iOS 8 binary trace remains archival
   corroboration only, not a prerequisite for the next safe touch work.
4. Firmware upload remains a separate explicit user decision. It is the first
   remaining action that would put non-idle command bytes on the controller.

## Reproducible public cross-check

The public iOS 10.3 unstripped J82 personality and driver binary were read
from `userlandkernel/ios-unstripped-kexts`, paths
`kexts/10.3/s8000/AppleMultitouchSPI.kext` and
`.../PlugIns/AppleMultitouchSPIJ82.kext`. They are a sibling-build cross-check,
not a substitute for the private iPad5,3 iOS 8.1 evidence recorded elsewhere
in this repository.
