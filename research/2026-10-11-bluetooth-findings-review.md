# Review of the research agent's Bluetooth findings (2026-10-11)

Reviewed: commits `ec34b5c` (iOS 8.1 AppleBluetooth start-up), `39328be` (Linux `hci_bcm`/`btbcm` order), `86977f0` (BCM firmware protocol) in `research/2026-10-10-d2207-public-static-analysis.md` and `research/j81-bluetooth-bringup.md`,
read against our own hardware results (`research/2026-10-10-bluetooth-gpio2-hardware-test.md`, rounds 1-4).

## What is new and solid
1. **iOS powers the radio at driver start and does nothing else automatically.** `BTReset::start()` (`0xffffff8002c4b930`) looks up `function-bt_reset`, `function-bt_wake`, `function-power_enable` (all optional), calls power-enable with 1, and registers
   `btreset`/`btwake`/`btpoweroff` character devices. No delay, no second rail or clock lookup, no UART or encoding handling in this driver; wake is asserted only while a client holds `btwake` open; J81 has no reset function. This matches the experiment we ran
   (power-enable high, BT_WAKE high) and confirms nothing in `AppleBluetooth.kext` is missing from it.
2. **Stock iPadOS opens the Bluetooth UART at 3 Mbaud from the first byte.** `BTServer` takes the `BaudRate` preference, else the ADT `transport-speed` (3,000,000 here), else 2.4 Mbaud; the mounted 12B410 root has no override. There is no 115,200 bootstrap phase in the production path.
3. Linux side: `hci_bcm` first-command rate is 115,200 and `max-speed` is only the later operating rate; `current-speed` is not consumed (a small future patch: read `current-speed` as `init_speed`).
4. BlueTool metadata: UART subversion `0x610c` is **BCM4350C2** to Apple (Linux `btbcm` says BCM4354 for the same id); the board's patch-RAM candidate is a private `BCM4350C2_..._Riesling_...hcd`; the 12B410 filesystem holds no standalone HCD. Firmware is needed only after HCI Reset and the version read succeed.
5. Firmware protocol envelope (Reset, version, `0xfc2e` Download Minidrv, HCD records, `0xfc18` baud change) is understood; nothing firmware-side can precede the first HCI response.

## What is stale or wrong in `j81-bluetooth-bringup.md` (written 2026-09-25, partly updated 2026-10-10)
- It says GPIO2's configuration is register `0x03e6`, that Apple's transaction is `03 e6 02`, that this write "demonstrably does not persist" and that D2207 ownership/lock state blocks it. **Superseded**: the correct register is `0x0402`
  (`research/j81-d2207-gpio-register-correction.md`, 2026-10-04); on 2026-10-10 the write `0x0402: 0x09 -> 0x0b` persisted and was reverted cleanly on the live iPad, three times. The PMIC write is not the blocker.
- "Linux sends HCI bytes but receives none while that line reads low" and "D2207 GPIO2 remained configured low": with the line high (and BT_WAKE high) the controller is still silent at every rate we can generate.
- "3 Mbaud transmit path has already worked on hardware": false. The old evidence is a transmitted-byte counter (14 bytes), which shows bytes left the UART, not at what rate. **Measured on 2026-10-10: a 3,000,000 baud request runs at ~1.47 Mbaud** (24 MHz / 16 limit).
- "Safest next experiment: passive SDA/SCL capture over a cold iPadOS boot to find `03 e6 02`": obsolete for the same reason (the write works); no extra measurement hardware is needed for it.

## The connection that changes the priorities
Put the agent's item 2 next to our UART measurement (research note, fourth round):
- iOS talks to this controller at **3 Mbaud from the first byte**;
- our UART3 can generate at most **~1.5 Mbaud** (it silently ran every "3 Mbaud" attempt at ~1.47 Mbaud, and 921600 at ~743 kbaud);
- our only accurate rate is 115,200, which iOS never uses against a cold controller.
So **every probe so far was at a rate the controller may not be listening to**: either a rate the hardware cannot generate (3 M -> 1.47 M) or one iOS does not use at power-up (115,200). The controller may be alive and simply unable to understand us.
This turns the UART speed from "later debt" into the **leading blocker**. (It is a hypothesis, not proven: a ROM that autobauds or answers at 115,200 would contradict it, and a controller silent at every rate for another reason is still possible.)

## Consequences and next steps
1. **How does iOS get 3 Mbaud out of this UART?** Decode the iOS 8.1 UART driver for the S5L8960X block (UCON clock-select bits, UBRDIV/UFRACVAL, any x8 oversampling or a faster input clock selected by the driver or PMGR) and compare with `drivers/tty/serial/samsung_tty.c` (S5L variant) and our DT
   (`uart`/`clk_uart_baud0` are two temporary 24 MHz `clkref` handles; measurement shows the real input clock at the divider is 24 MHz). This is the task for the research agent now (brief to follow).
2. Then a kernel change to run UART3 at 3 Mbaud, and re-run the probe (`boot/bt_uart_probe.py --speeds 3000000`) with power-enable and BT_WAKE high. A measurable test of the hypothesis: time a bulk transmit again (it must take N*10/3e6 s).
3. Open and not yet modelled: whether the controller needs a 32.768 kHz LPO/TCXO clock that Linux's `hci_bcm` would normally enable (J81's ADT lists none; unknown whether the module supplies it), and the later `current-speed`/HCD-name integration patches.
4. Keep as is: no reset GPIO, no host-wake IRQ, no PMIC provider rewrite, no guess of firmware names until the controller answers.
