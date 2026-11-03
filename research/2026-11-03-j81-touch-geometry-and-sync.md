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
