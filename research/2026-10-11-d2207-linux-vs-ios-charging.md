# J81 charging: Linux versus Apple's D2207 programming

**Date:** 2026-10-11  
**Scope:** static analysis only; no build and no hardware access  
**Target:** iPad Air 2 J81/T7001, D2207 PMU at I2C address `0x3c`

## Result

The Linux implementation programs only the USB **input** ceiling at `0x04c0`.
Apple separately programs the battery **charge-current** setting at `0x04c6`.
Linux neither reads nor writes `0x04c6`; its reported
`constant_charge_current_max` comes from configuration register `0x04cf`, not
the active charge-current register.

That is the most important remaining software difference. A `2400 mA`
`input_current_limit` therefore proves only that the PMIC may draw up to that
amount from USB. It does not prove that the battery charger was told to put a
useful current into the battery.

This does not yet prove that `0x04c6` is the present bottleneck. The boot chain
may have left it at a useful value, and the battery may instead be tapering or
the system may consume the available input power. The first next test is a
read-only capture of `0x04c6`, not a new write.

## Evidence and confidence

The exact iOS 8.1 J81 kernelcache is the same image used by the earlier
charging work:

```text
SHA-256 19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf
```

Its stripped `AppleD2207PMU` established the J81 register paths. The symbols
and method boundaries below were independently recovered from the public,
unstripped iOS 10.0 `AppleD2207PMU` and `AppleARMPlatform` binaries. The D2207
register ABI and formulas agree with the exact J81 code and with the live
`0x04c0`/`0x04cf` observations already recorded in this repository.

| Finding | Confidence |
| --- | --- |
| D2207 register addresses, masks and conversions | High: exact J81 code, public symbols and live reads agree |
| Apple writes active battery charge current through `0x04c6` | High: named public method and matching exact-J81 implementation |
| J81 thermal/voltage current table below | High: direct J81 ADT data plus the public table parser |
| High-level event and ramp policy | Medium/high: named AppleARMPlatform code; the public binary is newer than iOS 8.1 |
| `0x04c6` explains the present near-zero net charge | Open until it is read on the running iPad |

## D2207 power-source register map

This table covers every D2207 register directly accessed by the Apple
power-source methods, excluding unrelated PMU initialization, GPIO, LDO,
backlight and RTC code.

| Register | Apple operation | Meaning |
| ---: | --- | --- |
| `0x0010` bit 2 | read-modify-write | USB input-current suspend. Set for a requested input below 75 mA; clear otherwise. Hardware tests already confirmed that setting it removes roughly 100 mA of USB contribution. |
| `0x0060`-`0x006c` | 13-byte read | PMU status/event block used for USB/firewire detection, charging state, charge timeout/end flags and power-limited state. |
| `0x04c0` | read/write | USB input-current limit. Decode: code `0xfe` or above means 3262 mA; otherwise `75 + floor((100*code+7)/8)` mA. |
| `0x04c6` | write | Active battery charge-current setting. Low six-bit code is 50 mA per count. Apple writes a complete one-byte code after clamping it to the `0x04c7` ceiling. |
| `0x04c7` | read at attach | Hardware/board maximum charge-current code, low six bits. Apple caches it and will not program `0x04c6` above it. If the read fails, the public driver falls back to `0x1f` (1550 mA). |
| `0x04c8` | read, two writes | Charge-timer reset. Apple writes `old & 0x08`, then restores `old`; Linux has no equivalent. This is not a normal current-setting operation. |
| `0x04cf` | read | Configured charge-current ceiling, low six bits at 50 mA/count. J81 reads `0x3c`, or 3000 mA. It is not the active `0x04c6` setting. |
| `0x0500` | read/write | ADC channel/start control; channel in bits 5:0 and start in bit 7. |
| `0x0501` | read/write | Temporary ADC control; Apple clears it back to bits 2:0 after conversion. |
| `0x0502` | two-byte read | ADC result; 12-bit sample is `(byte1 << 4) | (byte0 & 0x0f)`. |

Two other relevant Apple methods are explicit no-ops: D2207
`setChargeVoltageLimit()` returns unsupported, and
`getChargeVoltageConfiguration()` returns zero. There is no missing battery
charge-voltage write to copy from this driver.

### Status bits actually consumed

Apple reads all 13 bytes starting at `0x0060`, rather than treating one byte
as a complete charger state. The public D2207 implementation uses:

- status byte 2 mask `0x03` as its charging-state mask;
- status byte 2 bit 2 and bit 4 as the two charge timeout/end state outputs;
- status byte 2 bit 5 together with status byte 12 bit 0 for
  `getUSBPowerLimited()`;
- status byte 12 bit 0 in its USB-detect interrupt path.

Linux currently exposes none of these status or online/present indications.
The BQ27545 gauge's `Charging` status is inferred from battery current and is
not a substitute for the D2207 status block.

## Apple's programming sequence

The relevant sequence is split between `AppleARMPMUCharger` (policy) and
`AppleD2207PMUPowerSource` (register operations):

1. `AppleARMPMUCharger` loads the board's charger limits, temperature/voltage
   curve, minimum useful input current and USB-input cap from ADT.
2. PMU and accessory interrupts plus the upstream Lightning/USB charger
   detection select an available input-current target. D2207 itself does not
   determine the charger type from `0x04c0`.
3. Apple ramps/debounces the input target and calls
   `setUSBInputCurrentLimit()`.
4. D2207 calibrates the nominal USB tier, updates `0x0010` bit 2, then writes
   `0x04c0`. Thus a nominal 2400 mA request is normally calibrated to about
   2325 mA by Apple's J81 table, rather than written as an exact 2400 mA.
5. Independently, `getChargeLimit()` chooses a battery charge-current target
   from battery temperature and voltage. `setCharger()` distributes the
   available current and invokes `setChargeCurrentLimit()`.
6. D2207 caps the requested charge current to 3150 mA, quantizes it in 50 mA
   steps, caps it again to `0x04c7 & 0x3f`, and writes `0x04c6`.
7. Status interrupts and periodic charging work handle timeout/end-of-charge,
   current backoff and charge-timer reset. Capacity reporting and display
   smoothing are separate from the PMIC current registers.

Apple's input-current ramp is also measurement-aware: the platform layer has
explicit current-limit step, debounce and backoff paths, including logs for a
measured VBUS current below the selected limit. Linux currently jumps directly
to one fixed input ceiling and never observes actual VBUS power.

## J81 board policy recovered from ADT

The private J81 ADT capture contains these non-identifying charger settings:

```text
usb-input-limit-max          2400 mA
min-charge-capable-current   1000 mA
charger-sleep-interval       300
ui-update-interval           40
charge-limits                3000, 2056, 1468, 881 mA
```

The `charge-currents` blob is three variable-length records. The public
AppleARMPlatform parser establishes the record format as a signed 16-bit
temperature range, a pair count, then `(battery millivolts, charge milliamps)`
pairs. Decoded for J81:

| Battery temperature | Battery voltage | Charge-current target |
| --- | ---: | ---: |
| 10.00-15.00 C | up to 4200 mV | 1468 mA |
| 10.00-15.00 C | above 4200 mV | 734 mA |
| 15.00-20.00 C | up to 4200 mV | 2936 mA |
| 15.00-20.00 C | above 4200 mV | 2202 mA |
| 20.00-45.00 C | all voltages | 2936 mA |

Outside a matching temperature record, the routine returns no charge-current
target. This is real battery thermal derating, distinct from reducing the USB
input ceiling.

The ADT also contains a "penalty box" with 75/80 percent SOC and
36/37 C thresholds, but `penalty-box-enable` is zero on J81. Therefore the
current Linux 80% cutoff is a deliberately conservative project policy, not a
reproduction of active J81 iPadOS policy.

## What Linux does today

`kernel/patches/0010-j81-d2207-readonly-charger.patch` provides only:

- `INPUT_CURRENT_LIMIT` from `0x04c0`;
- `CONSTANT_CHARGE_CURRENT_MAX` from `0x04cf`.

Patch `0017` makes only `INPUT_CURRENT_LIMIT` writable. The boot policy then:

- writes 2400 mA to `0x04c0` below 80% and below 42 C;
- writes 500 mA at/above either threshold or when telemetry is unavailable;
- never reads D2207 charger state or actual VBUS power;
- never reads/writes active battery charge current at `0x04c6`;
- never reads `0x04c7` or handles the charge timer;
- has no USB/accessory charger detection or current ramp/backoff.

The important conceptual mismatch is that Linux's temperature and capacity
policy reduces **input power**, while Apple selects a temperature/voltage-safe
**battery charge current** and separately manages the input budget.

## Smallest safe next work

### 1. One read-only hardware capture

Before changing policy, record these bytes while the battery is preferably at
30-60%, first idle and then with display/Wi-Fi load:

```text
0x0010
0x0060-0x006c
0x04c0
0x04c6
0x04c7
0x04c8
0x04cf
```

At the same timestamps record BQ27545 current, voltage, temperature, capacity
and status. Decode `0x04c6`, `0x04c7` and `0x04cf` as
`(raw & 0x3f) * 50 mA`.

Decision:

- If `0x04c6` is already near 3000 mA, charge-current programming is not the
  present limiter. Implement VBUS ADC measurement next and separate system
  consumption from battery acceptance/tapering.
- If `0x04c6` is zero or materially below the J81 table's target, Linux is
  missing the active charger programming and has a concrete implementation
  target.
- If `0x0010` bit 2 is set, clear ownership/suspend logic is the first bug;
  do not compensate by increasing either current register.

This capture uses ordinary PMIC reads and needs no new kernel if the existing
diagnostic shell is available.

### 2. Minimal developer change after that capture

Add read-only reporting before any new write:

- expose active `CONSTANT_CHARGE_CURRENT` from `0x04c6`;
- expose the real hardware cap from `0x04c7` as
  `CONSTANT_CHARGE_CURRENT_MAX`;
- retain `0x04cf` in diagnostics as the configured ceiling;
- extend `tablet-status`/the logger with those three raw and decoded values.

Do not implement the whole Apple policy yet. If the read proves `0x04c6` is
too low, the smallest controlled write follows Apple's exact setter:

```text
code = min(floor(min(request_mA, 3150) / 50), reg_0x04c7 & 0x3f)
write one byte to 0x04c6
```

Start with a bounded value already below both the J81 table and the observed
3000 mA configuration, keep `0x0010` bit 2 clear, monitor battery/VBUS
telemetry, and restore the original byte after the test. Full charger-type
detection, Apple's ramp algorithm and charge-timer handling should be added
only if this measurement proves they are needed.

### 3. VBUS measurement, separately

Apple measures VBUS current on ADC channel 9 and voltage on channel 19:

```text
current_mA = floor(raw * 52800 / 1000)
voltage_mV = floor(raw * 96192 / 1000)
```

Starting a conversion writes `0x0500`/`0x0501` and waits for the ADC-complete
interrupt, so it is not safe to fake as a shell-only read. Implement it in the
PMIC kernel driver with serialization and interrupt completion. This is the
measurement needed to distinguish high system consumption from battery
charge acceptance after the active `0x04c6` setting is known.

## Bottom line

The present 2400 mA setting answers only "how much may enter from USB?" The
missing observation is "what battery charge current is actually programmed?"
Apple answers that with `0x04c6`; Linux currently does not. Reading that one
byte is the fastest discriminating next step.
