# J81 touch: firmware geometry and GPIO55 timing (2026-11-03)

This follows the Z3 runtime tests in [the touch run log](2026-11-01-orchardlinux-org-review.md), where GPIO55 peripheral function 1 let the N1 firmware execute but report `0xa1` contained six zero bytes and report `0xd9` contained 16 zero bytes. The same driver discovered a 14745×19657 surface with GPIO55 function 2/3. A test-only host-side surface fallback still produced no contacts during confirmed swipes with either firmware version.

## Firmware read path

I validated the private 12B410 HBPP packet's length and checksums with `boot/touch_fw_rebuild.py`, reversed each 16-bit payload pair to recover ARM/Thumb instruction order, and decompiled the report handler. The first decoded word is an ARM reset-vector `ldr pc` instruction; the handler has a plausible Thumb prologue. The raw firmware and decompiler database stay in ignored `artifacts/live/private/`.

- Report `0xa1`, handler at payload offset `0x6f12`, copies six bytes from the address held in RAM at `0x403c08`. A write handler for `0xa1` at offset `0x7642` can replace those bytes, but does not appear to trigger initialization.
- Report `0xd9` reads a pointer held in RAM at `0x403c20`, then takes the 32-bit surface width and height at offsets `+0x20` and `+0x24` and four 16-bit bounds fields at `+0xdc` through `+0xe2`. Thus a zero `0xd9` can be a real reply from zero runtime state, even when the firmware and SPI transaction are otherwise alive.
- An apparent initialization chain at offsets `0xdb8e` → `0x12a4` → `0xd9ee` writes width `0x3999` (14745) and height `0x4cc9` (19657) to a structure based at RAM `0x4043fc`. These match the live nonzero `0xd9` result. The analysis has **not** established that the pointer at `0x403c20` refers to this structure, that this chain runs in the successful boot path, or why function 1 yields zeros.
- The private 19H422 HBPP packet validates and has the same payload length. It differs from 12B410 at only three payload bytes (`0x741b`, `0x7443`, `0xe489`); the first two encode the observed firmware version change from `0x381` to `0x382`. The `0xa1`/`0xd9` read cases and geometry constants are unchanged. That is consistent with the same zero-geometry behavior observed on both versions.

The `0xd3` sensor identity is largely assembled from constants in the handler, so its valid 40×30 response does not establish that the runtime surface structure was initialized. Firmware upload and a registered Linux input device likewise do not establish scanning.

## Live GPIO55 timing

With the controller unpowered (`LDO14=0x00`, touch clock gated), I routed GPIO55 from its saved `0x00072a82` to peripheral function 1 using `touch-diag dsync 1`. A static AArch64 read-only `/dev/mem` sampler counted pad-register bit-0 transitions for two consecutive two-second windows:

| Window | Samples | Rising | Falling | High time | Mean rising-edge period |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2,639,979 | 60 | 60 | 50.0% | 33.34 ms |
| 2 | 2,637,260 | 60 | 60 | 50.0% | 33.34 ms |

This is a stable **30 Hz digital input indication** on GPIO55 while muxed to function 1, stronger evidence than the earlier sparse high/low samples that the Linux display path generates a periodic signal. It is not an electrical measurement at the touch chip, an iPadOS reference waveform, or proof that 30 Hz and this phase are suitable for the N1 scanner. Apple's touch-controller architecture describes display SYNC as a possible scan-timing input ([US20150035768A1](https://patents.google.com/patent/US20150035768A1/en)), but does not give this J81 pin's required waveform.

The sampler made no writes. `touch-diag dsync-restore` restored GPIO55 exactly to `0x00072a82`; the subsequent status read showed LDO14 `0x00`, clock `0x800002ee`, and `apple_z2` unloaded. The sampler source and binary remain ignored test artifacts, not part of the product driver.

## Implication

The specific “GPIO55 has no changing signal under Linux” idea is weakened. The higher-value question is why the firmware's runtime data is zero on the function-1 path, and whether the 30 Hz signal matches iPadOS at the controller. A native iPadOS GPIO55/ATN timing trace or a verified way to inspect the runtime pointer and structure would distinguish incorrect sync timing from firmware initialization or report-transport failure. Do not write guessed values to report `0xa1` or copy the 14745×19657 descriptor into the shipped driver on this evidence.

## Read-only iPadOS reference (later on 2026-11-03)

After a forced reboot from the RAM-booted Linux image, the same J81 booted its installed iPadOS **15.8.5**. Martin unlocked it, trusted the Mac, and confirmed that taps and swipes work normally. The standard USB diagnostics relay, queried through `pymobiledevice3 diagnostics ioregistry --ioclass AppleMultitouchN1SPI`, exposed these non-identifying runtime properties:

| Property | Live iPadOS value |
| --- | --- |
| `IOClass` | `AppleMultitouchN1SPI` |
| `Family ID`, interface, sensor rows × columns | 22, 1, 40 × 30 |
| `Constructed Firmware Version` | `0x0382.bin` |
| `Sensor Region Param` (`0xa1`) | `00 00 05 00 00 02` |
| `Sensor Surface Descriptor` (`0xd9`) | `99 39 00 00 c9 4c 00 00 90 ff 90 ff ac 38 e2 4b` |
| Surface width × height | 14745 × 19657 |
| `IOPowerManagement.CurrentPowerState`, `ResetCount` | 1, 0 |

The descriptor and region parameters stayed identical in a second IORegistry query after swiping. This is the strongest direct reference yet for the expected J81 runtime data. It matches the nonzero Linux function-2/3 discovery and differs from the all-zero Linux function-1 replies. The installed iPadOS is 15.8.5; the 19H422 firmware tested under Linux was extracted from 15.8.8 and also identified itself as `0x382`.

The same read-only USB relay supplied syslog. A second, synchronized swipe capture contained **106 `backboardd(MultitouchHID)` dispatch events** (54 with `Touching=1`, 52 with `Touching=0`) over about 30 seconds. This verifies that native touch reporting works on the panel. The full IORegistry and syslog captures, including potentially identifying material, are kept only in ignored private artifacts; this note contains no calibration bytes or device identifiers.

The diagnostics service exposes the ADT `function-display_sync` record and GPIO provider metadata, but **not GPIO55's live pad register or waveform**. Thus this software-only, non-jailbroken path gives runtime touch reference values and events, not the requested electrical timing comparison. Reading GPIO55 during iPadOS would require a privileged on-device method or a passive physical probe; a rootless jailbreak would modify the iPadOS installation and was not used.

## Linux runtime geometry timing test (later on 2026-11-03)

On the Z2 payload (`j81.run_id=d8b3f19e…`), I loaded the bounded-PIO `spi_apple` module and the 19H422 Apple-order/proximity firmware, with LDO14 and the touch clock held on. A test-only `apple_z2` module (SHA-256 `f0ab6291…`) selected GPIO55 function 1 at the wake-to-dummy point, substituted the known surface **only for host-side discovery**, then polled the report queue every 100 ms and reread `0xa1` and `0xd9` every 50 polls. Discovery initially received zero `0xa1` and `0xd9` data. All six later samples, spanning approximately 5–30 seconds, returned the exact nonzero iPadOS `0xa1` and `0xd9` values above. The first 300 queue reads found no nonempty report. This established that the geometry zeros are transient, but the periodic wake and queue reads could have contributed.

I unloaded that module, released the rail and clock to their saved values, then started a separate test from reset. The second test-only module (SHA-256 `729b5aa8…`) had **no descriptor substitution and no periodic poll**. It waited six seconds after reading the region report and before requesting `0xa1` and `0xd9`. Both reports returned the exact nonzero reference values, `apple_z2_set_surface()` accepted the real descriptor, and the input device bound. Therefore time alone, without queue polling or a host-side descriptor fallback, is sufficient to get valid geometry in this boot sequence. The minimum required delay has not been measured; six seconds is a diagnostic bound, not a proposed production constant.

The first test's poll count reached at least 1,850 with zero nonempty frames and GPIO84's interrupt count stayed at 2. Its finger swipe was not synchronized with the log collection, so the contact conclusion rests on the following two captures with the delayed module:

- With `poll_ms=0`, Martin confirmed swiping for most of a synchronized 30-second window. GPIO84 IRQ 57 stayed at `2/0/1` across the CPUs, and `/dev/input/event1` yielded zero bytes.
- After unloading, restoring the rail and clock, and starting again from reset, the same six-second-delay module bound with the real descriptor and `poll_ms=100 poll_wake=1`. Martin confirmed swiping during another synchronized 30-second window. IRQ 57 stayed at `2/1/1`, `/dev/input/event1` yielded zero bytes, and the periodic queue reader reached at least 600 reads with zero nonempty frames. No poll frame or poll error was logged.

Thus delayed geometry is a separate, fixable discovery problem, while the contact-generation problem remains. The empty queue rules out a missing IRQ as the sole explanation under these startup conditions. The module was unloaded and the rail, clock and GPIO55 restored. Raw kernel logs and test binaries remain in ignored private artifacts.

GPIO84's pad word changed from `0x00070381` before the first probe to `0x0000038f` after module removal. Inspection of `pinctrl-apple-gpio.c` explains the exact difference: IRQ startup selects group 0 (clearing group bits 18:16 from 7), and IRQ masking selects mode 7 (setting bits 3:1 from 0 to 7). The data bit stays high, pull-up bits and input-enable bit remain set. This is the GPIO IRQ driver's expected released state, not evidence of a stuck-low ATN or an additional touch-controller failure. No raw pad write is needed to restore those fields for another Linux probe.
