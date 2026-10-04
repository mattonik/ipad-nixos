# J81 audio/sensor topology: comparison against the private J81 ADT

Date: 2026-10-04. Source: the existing private J81 ADT capture (already on the
laptop under ignored `artifacts/adt/`; no new boot, no device access). This
closes the "local J81 topology comparison" step in
[`j81-audio-sensors-source-survey.md`](j81-audio-sensors-source-survey.md).

Only reviewed, non-identifying structure is recorded: node presence,
compatible strings, resource words and interrupt/clock-gate indices. No
calibration, serial, radio address or firmware-name data is included. Values
are `arm-io`-relative as stored in the ADT, not converted to Linux DT cells.

## Result

**All 20 nodes in the J82 sibling survey exist on J81 with the same parent
layout.** The survey's topology assumptions therefore carry over to J81 as
*presence*; they are still not driver evidence.

| Node (under `/arm-io`) | J81 observation |
| --- | --- |
| `uart8`, `uart8/oscar` | present; oscar compatible `apple-osr1`/`oscar`, `oscar-version 0x00020000`. uart8 clock-gate `0x58`, IRQ `0xa6`. |
| `spi1`, `spi1/audio-codec` | present; spi1 clock-gate `0x4b`, IRQ `0x99`; codec is chip-select 0. |
| `i2c1/audio-speaker0`, `audio-speaker1` | present; I2C addresses `0x31` and `0x34`, GPIO interrupts `0x08` and `0x09`. |
| `i2c2/als1`, `i2c2/als2` | present; **`compatible = als,ct819`** on both; I2C addresses `0x49` (als1) and `0x29` (als2); GPIO interrupts `0x67` and `0x6e`; both carry `probe-for-hardware = 1`. |
| `i2s-switch` | present; compatible `i2s-switch`/`i2s-swi960x`. |
| `mca0`, `mca1`, `mca3`, `mca4` | present; compatible `mca,t700l8950x`, `mca-version 1`; clock-gates `0x40`, `0x41`, `0x43`, `0x44`; two `reg` ranges each, the second ~0x2000-sized and offset from the first. |
| `mca0/audio-codec`, `mca1/audio-codec-voice`, `mca3/audio-speaker0`, `mca4/audio-bluetooth` | present. |

## What this changes

- **CT819 ambient light remains the least-coupled first target**, now with
  J81-confirmed addresses. `probe-for-hardware = 1` means Apple itself
  probes for the part, so it is **not known which of the two (or both) is
  populated on this Wi-Fi-only iPad**. Do not assume a device at either
  address.
- A read-only **I2C address probe** of `0x29` and `0x49` on bus 2 is the only
  experiment this suggests. It needs `i2c2` described, powered (clock-gate
  `0x48`) and enabled in the J81 DT first, which is separate groundwork; the
  active Hoolock board DT does not do this today. Not started.
- The MCA finding stands: a compatible-string-only enablement would be wrong.
  The old `mca,t700l8950x` layout has a small second range that the modern
  driver's RXB DMA assumption does not match.
- Nothing here justifies a build change. No codec, speaker amplifier, motion
  coprocessor or ALS driver exists in the pinned Hoolock tree.

## Status labels

- Node presence, compatible strings, I2C addresses, interrupt and clock-gate
  indices: **evidence** (private J81 ADT).
- Which ALS part(s) are populated, codec/amplifier part numbers on J81, and
  every power sequence: **unknown**.
