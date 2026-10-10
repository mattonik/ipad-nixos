# Bluetooth: first controlled GPIO2 (`0x0402`) test on hardware, 2026-10-10

Context: the research agent's static decode (`research/2026-10-10-d2207-public-static-analysis.md`, commit `c535a45`) showed the J81 ADT has none of the PMU GPIO default properties, so the only remaining
Bluetooth power step is the `function-power_enable` call (PMU GPIO2, register `0x0402`). Apple's `_setGPIOFunction` computes `b = (b & 0x1d) | 0x02` for "high" (`0x09 -> 0x0b`). The user approved this single write
for the run (2026-10-10, in chat); the plan (read first, one write, immediate and delayed readback, test, revert, abort on any surprise) was followed.

## Setup (no rebuild, nothing persistent)
Static `btattach` and `i2c-tools` (flake package `bt-userland-static`, GC root `artifacts/live/gcroot-bt-userland`) were pushed to the iPad's RAM (`/tmp/bt`) over the USB link from a short-lived HTTP server; the running payload was the production base (P4).
i2c bus 0, PMU address `0x3c`, 16-bit register addresses (`i2ctransfer -f -y 0 w2@0x3c HI LO r1@0x3c`).

## Baseline (read-only)
`0x0402 = 0x09`, `0x0403 = 0x0b` (Wi-Fi `reg_on`, high), `0x0063 = 0x20`, `0x0010 = 0x00`, `0x04c0 = 0xba` (2400 mA), battery Charging. `0x0402 = 0x09` is exactly the value the agent's decode predicted.

## The write
`i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b`: rc 0; readback `0x0b` immediately and after 3 s (it holds, unlike every earlier write to the wrong address `0x03e6`). Side effects: none on charging (`0x04c0`, `0x0010` unchanged, status Charging),
`0x0403` unchanged. One observation: the GPIO data register `0x0063` changed `0x20 -> 0x60` (bit 6, not GPIO2's bit 2) a few seconds after the write and went back to `0x20` after the revert, i.e. it follows the GPIO2 config change; unexplained, maybe a coupled input.

## The Bluetooth attach
`btattach -B /dev/ttySAC1 -P bcm -S 3000000` (the project's established command): `hci0` registered (HCI UART protocol layer works), but the chip stayed silent: `Bluetooth: hci0: command 0xfc18 tx timeout`,
`BCM: failed to write update baudrate (-110)`, then `BCM: Reset failed (-110)` — the same signature as every earlier attempt. So GPIO2 at `0x0b` is not sufficient on its own (at least with this attach recipe).

## Revert
`0x0402 <- 0x09`: rc 0, readback `0x09` immediately and after 3 s, `0x0063` back to `0x20`, `0x0403`/`0x0010`/`0x04c0` unchanged, battery Charging. Final state equals the baseline.

## What was not done
A raw HCI-reset probe straight on `/dev/ttySAC1` at several baud rates (stty + a 4-byte write + read-back) was blocked by the tool's auto-mode safety classifier and was not run.

## Hypotheses for next steps (nothing here is tested)
1. **Baud/flow control:** `btattach -S 3000000` sets the *initial* speed; the chip's UART may start at 115200 (or need RTS/CTS handling). The first command (`0xfc18` update-baudrate) is sent at the initial speed, so a wrong initial speed alone gives this exact failure. A raw reset at 115200/921600/3 M with and without flow control separates "chip silent" from "wrong speed".
2. **Other control lines:** Apple has `function-bt_reset` and `function-bt_wake` (strings in the kernelcache, the agent's note) in addition to `power_enable`; whether the J81 ADT carries them as AP GPIOs (pinctrl) has not been checked against the captured ADT.
3. **Timing:** the chip may need a defined delay between power-up and the first UART traffic, or a reset pulse after power; our attach ran seconds after the write.
4. **Shared power:** BCM4350 Wi-Fi and Bluetooth are one chip; Wi-Fi is up (`reg_on` high), so Bluetooth may depend on a different gate (the `0x0063` bit-6 coupling is a hint worth decoding).

## Second round (same day): ADT check, GPIO map, raw UART probe sweep

User authorised "all the tests you can do with the attached iPad" and the permissions rule for the probe scripts. The same `0x0402` write (`0x09 -> 0x0b`, then revert) was repeated for the sweep; nothing else was written.

**ADT (captured J81 ADT, `artifacts/adt/...j81.adt`, node `bluetooth,n88`; MAC values not recorded here):** `function-power_enable` = PMU (phandle 0x4e) OIPG pin 2; **`function-bt_wake` = AP GPIO (phandle 0x1f) OIPG pin 0xa4 = 164**, flags `01 01 00 00`;
`transport-speed` 0x2dc6c0 (3,000,000 baud), `transport-encoding` 3, `coex` 2. No `bt_reset` or host-wake function exists on this board. UART3 uses pins 14 (TX) and 32 (RTS), function `periph2`.
Runtime pinctrl check (debugfs, read-only): pins 14 and 32 are claimed by `20a0cc000.serial`; **pin 164 (BT_WAKE) is UNCLAIMED** (no driver owns or drives it); pin 165 is the Wi-Fi `t7000-device-wake` (out, high).

**GPIO bank before/after asserting `0x0402 = 0x0b`:** configs `0x0400..0x0410` identical except `0x0402` (`0x09 -> 0x0b`); data bytes `0x0060..0x0066` identical except `0x0063` (`0x20 -> 0x60`, bit 6), which follows the config write and returns on revert. Baseline configs: `09 49 09 0b 09 da ba 7b b9 ea fa 7b f8 c8 c8 7b 01`.

**Raw HCI Reset probe (`boot/bt_uart_probe.py`, 4-byte standard command only):** control with `0x0402 = 0x09`: silence at 115200 and 3000000 baud, with and without RTS/CTS. Powered (`0x0b`, 2 s after the write): **silence at 115200, 921600, 1500000, 3000000, with and without RTS/CTS** (0 bytes in 3 s each).
So the earlier `btattach` failure is not a baud-rate or flow-control problem: with only GPIO2 asserted the chip does not answer at any speed.
(Retracted: a UART status line `RTS|DTR|DSR|CD` without CTS looked like a chip-not-ready clue, but it is identical before and after the revert.)

**Revert verified:** `0x0402 = 0x09`, `0x0063 = 0x20`, `0x0403`/`0x0010`/`0x04c0` unchanged, battery Charging (the gauge status flips between Charging/Discharging as the net current crosses zero; limit stayed 2400 mA).

## Leading hypothesis now: BT_WAKE (AP GPIO 164) is never asserted
Apple's Bluetooth node lists `function-bt_wake` next to `power_enable`; BCM controllers sleep their UART when the wake line is low. Nothing in our system drives pin 164. Testing it needs a write that does not exist yet:
no `devmem` tool, no sysfs GPIO, no libgpiod on the iPad; `/dev/mem` exists. Options: a tiny static poke tool for the pinctrl register of pin 164 (Apple GPIO register `base + 4*pin`, base `0x20e300000`), or the proper route (DT: a `bluetooth` serdev child with `device-wakeup-gpios` on pin 164 plus a D2207 PMU GPIO provider for `power_enable`: plan BT-3).
Driving an AP GPIO is a new write category: it needs its own explicit approval for the run (like DEVICE_WAKE on pin 165).

## Third round (same day): BT_WAKE (AP GPIO 164) and power-enable both asserted

Run by the user from their own terminal (`boot/bt_wake_experiment.py`; the tool-use classifier blocked me from the pad write, so the user ran the self-restoring script, commit `3f49194`). Tool: `pinpoke` (static, `/dev/mem`, reads any pin, may write only pin 164; flake package `pinpoke-static`).
- Baseline: pin 164 pad register `0x00072602` = output, **driven low** (set by iBoot); `0x0402 = 0x09`, `0x0010 = 0x00`, battery Charging. Pin 165 (Wi-Fi wake) `0x00072603` = out, high, as expected.
- `pinpoke high 164` -> `0x00072603` (readback OK); `0x0402 <- 0x0b` -> readback `0x0b`.
- Raw HCI Reset probe, both lines asserted: **0 bytes** at 115200, 921600 and 3,000,000 baud, with and without RTS/CTS. `btattach -P bcm -S 3000000`: `hci0` registers, then `command 0xfc18 tx timeout`, `BCM: failed to write update baudrate (-110)`, `BCM: Reset failed (-110)` — unchanged.
- Restore verified: `0x0402 = 0x09`, pin 164 `0x00072602`, `0x0010 = 0x00`, `0x04c0 = 0xba`, battery Charging.

**Conclusion:** neither BT_WAKE low nor a missing baud/flow-control setting explains the silent chip: with power-enable and BT_WAKE both high the Bluetooth UART still receives nothing.

**UART pad routing (read-only, `pinpoke read`):** pin 14 (TX) `0x00072641` and pin 32 (RTS) `0x00072643` are peripheral function 2 (set by our DT/ADT); the ADT lists only those two as `function-*` for UART3. Pins 15 (RX, presumably) and 33 (CTS, presumably) read `0x00070221`:
peripheral function 1, input enabled, as left by iBoot. Pin 34 (UART5 TX / battery HDQ) `0x00072621` has the same function-1 form. So RX/CTS do not look like plain GPIOs; the pad routing is not an obvious fault (but it is also not verified by signal measurement).
Still unexplained clue: the UART's modem-status line shows `RTS|DTR|DSR|CD` and never CTS, both unpowered and powered, i.e. the chip's own RTS output never indicates "ready" (a live BCM controller normally asserts it once its UART is up).

## What is left to explore (static analysis first, then maybe hardware)
1. The iOS 8.1 Bluetooth driver's power-up sequence after `function-power_enable`: waits, whether it toggles `bt_wake`, whether a 32 kHz clock or other PMU rail must be enabled first, and what `transport-encoding = 3`, `coex = 2` and `transport-speed = 3 Mbaud` select (a mode that the first HCI command must match).
2. Whether BT_REG_ON on this module is really PMU GPIO2: GPIO2's config goes `0x09 -> 0x0b` and `0x0063` bit 6 follows it; decode what that data bit is.
3. The Wi-Fi side: the chip is a Wi-Fi+BT combo that is powered via `reg_on` (GPIO3, high); a BT-specific rail/clock may be shared with the Wi-Fi power sequencing (e.g. BT only comes alive after the Wi-Fi firmware sets a BT-enable bit through the chip's own registers: on some BCM4350 designs the Wi-Fi firmware must report BT coex; the C2 firmware has a `bt` coex/`btcoex` setting).
4. UART clock/baud accuracy: `base_baud = 0` in the Samsung UART driver; check the real divisor for 115200/3 Mbaud (HDQ flakiness on UART5 hints at baud/timing error).
