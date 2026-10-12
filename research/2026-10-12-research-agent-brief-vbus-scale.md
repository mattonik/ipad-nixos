# Brief for the research agent: confirm the D2207 VBUS ADC scale (our hardware says the documented factors are 64 times too large)

Project: Linux on an iPad Air 2 (J81, A8X/T7001). Repo `/Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos`. Method: memory note "Apple firmware archaeology technique", `tools/ghidra/README.md`. A scratch Ghidra project of the iPad5,3 12B410 `__PRELINK_TEXT` (base `0xffffff8002593000`) was used by the last agents and may still exist; otherwise re-import it from `firmware/j81-12B410/ipsw/` (about 10 minutes flat). No downloads without asking the user.

## Read first
`research/2026-10-11-d2207-vbus-adc.md` (the recovered ADC transaction and the hardware validation sections at the end), `research/2026-10-11-d2207-linux-vs-ios-charging.md`, `docs/plans/2026-09-26-tethered-tablet-and-charging.md` ("Recovered D2207 VBUS ADC interface").

## What the hardware says
Patch 0099 starts an ADC conversion on channel 19 (VBUS voltage) and channel 9 (VBUS current), reads the two result bytes at `0x0502`, decodes `raw = (byte1 << 4) | (byte0 & 0x0f)` (12 bits) and multiplies by the documented factors (88 mV and 52.8 mA per count). On the live iPad, charging from a USB 2.0 source (about 5 V, about 0.5 A):
- voltage raw about 3541 -> 311 V at 88 mV/count (impossible);
- current raw about 591 (and 577) -> 31 A at 52.8 mA/count (impossible).
Dividing both by 64 gives 4.87 V and about 0.49 A, which matches a bench-plausible USB source and a later 10-sample run (4.87 V, 476-484 mA flat, 4.38 V / 1.04 A in another source state). A 12-bit sample cannot be 88 mV/count (that would be a 360 V full scale). So either the conversion functions divide by 64 (a fixed-point shift) somewhere, or the sample is not "raw >> 0", or the first result byte holds more fractional bits.

## Questions (static analysis of AppleD2207PMU and AppleD2207PMUPowerSource)
1. **Exact conversion for channel 19 and channel 9.** Decompile the voltage conversion at `0xffffff8002b49200`, the current conversion at `0xffffff8002b494c0`, the jump-table targets (`0xffffff8002b49324` for channel 19; find channel 9's), and the shared divide-by-1000 path. Show the arithmetic in C-like form: input (raw sample as stored by `0xffffff8002b4821c`), shifts, multiplications, divisions, the unity multiplier `0x10000` the wrappers (`0xffffff8002b4cbdc`, `0xffffff8002b4cbf4`) pass, and the units of the result. Is the result in mV/mA, or in some fixed-point unit (for example mV x 64, or 16.16)?
2. **Sample decode.** Does `readADCGated` (`0xffffff8002b4821c`) really produce `(byte1 << 4) | (byte0 & 0x0f)`, or a wider value (for example a 16-bit combination with fractional bits), and what do the wrappers do with the value before it reaches `measureVBUSVoltage`/`measureVBUSCurrent` callers (the power-source code that publishes millivolts / milliamps)? Check how the callers use the return value, including the `AppleD2207PMUPowerSource` property that publishes input current in mA.
3. **Conclusion.** State the exact formula with units that gives about 4.9 V for raw 3541 and about 0.49 A for raw 591 (if the arithmetic supports it) and whether it is a divide by 64 (a shift by 6), with evidence labels E (read in code) / I / U. If the code gives something different, say what.

## Deliverable
Append a section "Scale confirmed from the J81 code" to `research/2026-10-11-d2207-vbus-adc.md` (or a new note `research/2026-10-12-d2207-vbus-scale.md` linked from it) with the formulas, function addresses and a one-line recommendation for patch 0099 (what constants to use in microvolts and microamps). Evidence = function addresses/offsets and short constants; never raw firmware bytes or decompiler dumps. Path-limited commit with the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Use `/opt/homebrew/bin/python3`, `command ls`; no hardware access.
