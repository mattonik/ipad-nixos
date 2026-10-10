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
