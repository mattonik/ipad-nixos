# Brief for the research agent: how does iOS run the Bluetooth UART at 3 Mbaud, and why can Linux only reach ~1.5 Mbaud?

Read first: `research/2026-10-11-bluetooth-findings-review.md` (the connection that makes this the priority), `research/2026-10-10-bluetooth-gpio2-hardware-test.md` (rounds 1-4, measurements), `research/j81-bluetooth-bringup.md` (your own earlier notes; the stale parts are listed in the review).
Project: Linux on an iPad Air 2 (J81, A8X/T7001). Repo: `<repo>` (branch `main`). Method background: memory note "Apple firmware archaeology technique" (ipsw + Ghidra), `tools/ghidra/README.md`.

## The problem in one paragraph
The Bluetooth controller (BCM4350 combo, UART3 at `0x20a0cc000`, Linux `ttySAC1`) never answers an HCI Reset, although both its control lines are asserted (power-enable PMU GPIO2 = `0x0402`, BT_WAKE = AP GPIO 164; both verified on the live iPad).
iOS opens this UART at **3,000,000 baud from the first byte** (`BTServer` reads the ADT `transport-speed`; no 115,200 phase). Our UART cannot generate that rate. Measured on the running iPad (drained-transmit timing, chip unpowered, no flow control):

| requested | actual |
|---|---|
| 115,200 | ~115,000 (accurate) |
| 921,600 | ~743,000 |
| 1,500,000 | ~1,460,000 |
| 3,000,000 | **~1,470,000** |

Our UART divides a 24 MHz input by 16 x (UBRDIV+1), so the ceiling is ~1.5 Mbaud; every "3 Mbaud" probe was really ~1.47 Mbaud and every other probe was at a rate iOS never uses on a cold controller. Hypothesis (not proven): the controller is alive but cannot understand us.
We need to know exactly how iOS produces 3 Mbaud so Linux can do the same.

## Your job: static / offline analysis only (no hardware, no builds, no commits of private data)
Write `research/2026-10-11-<topic>.md` for each question that yields something (function addresses/offsets and short register values as evidence; **no raw firmware bytes, decompiler dumps or device identifiers**).
Proposals must say how they would be tested with what exists (see "Test method").

1. **iOS UART driver, baud programming.** In the iPad5,3 iOS 8.1 (12B410) kernelcache (SHA-256 `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`; existing Ghidra project `prelinktext`) find the driver for the Samsung-style UART (ADT `compatible = uart-1,samsung`,
   `uart-version = 1`, class probably `AppleSamsungSerial` / `AppleS5L8960XSerial` or a PL011-like successor; the Bluetooth UART client path is `AppleBluetooth`/`BTServer` -> serial service). Decode exactly what it writes to the UART registers for a requested rate: UCON (clock select bits, mode), UBRDIV, UFRACVAL,
   any oversampling/divider-mode bit, UMCON/flow control; and what it computes the divider from (a hard-coded 24 MHz, a PMGR clock rate it reads, `clock-ids`). Specifically answer: **how is 3,000,000 baud reached** (faster input clock, 8x oversampling, fractional divider, a different `clk_sel` source)?
2. **The clock feeding the baud generator.** The ADT uart3 node has `clock-ids` (`15 01 00 00 04 00 00 00`), `clock-gates` = 0x53 and `reg` 0x20a0cc000. Which PMGR/clock-tree entry is the baud-rate source on T7001, what rates can it be set to, and does iOS configure it (register, divider) when it opens the port? Compare with how our device tree models it
   (`kernel/patches/0001-t7001-add-uart3-node.patch`, `0002-...`: `uart` and `clk_uart_baud0` are two temporary 24 MHz `clkref` handles; the measurement shows the real input at the divider is 24 MHz).
3. **Linux driver comparison.** Read `drivers/tty/serial/samsung_tty.c` in the pinned tree (`/nix/store/*-linux-hoolock-pcie-j81-wifi-h1b-t7001-source`, or `artifacts/live/gcroot-h1b-source`) for the `apple,s5l-uart` variant: how it picks the clock and computes UBRDIV/UFRACVAL, which clock names it expects, and what limits the rate. Propose the smallest change
   that makes 3 Mbaud work: DT only (clocks / `assigned-clock-rates` / a different clock reference), or a driver change (oversampling mode, clock select). Check whether upstream Asahi (M1) or Hoolock have anything for higher-speed Bluetooth UARTs on this block.
4. **Secondary: the 32.768 kHz question.** Linux `hci_bcm` optionally enables a 32.768 kHz LPO/TCXO clock before power-up; J81's ADT lists none for the Bluetooth node. In the iOS drivers (AppleD2207PMU, AppleBluetooth, AppleARMPlatform, the PMU/PMGR clock-out code) is there any 32 kHz output that iOS enables at boot for the radio module
   (a PMU clock-out pad, an AP clock-out)? If the module needs an external sleep clock, the controller could be dead regardless of baud. The "KLCT" (touch 32.768 kHz from 24 MHz, divisor 732) analysis in `docs/plans/2026-09-09-j81-touch-spi3.md` shows the SoC can synthesize such a clock; check whether the Bluetooth path uses a similar one.

## Test method (what the user and I can do afterwards)
- Bulk-transmit timing: `stty -F /dev/ttySAC1 raw -echo -crtscts clocal SPEED`, `dd if=/dev/zero of=/dev/ttySAC1 bs=1000 count=N`, time with `/proc/uptime`; a correct rate takes N*10/SPEED seconds (`research/2026-10-10-bluetooth-gpio2-hardware-test.md`, fourth round).
- Probe: `boot/bt_uart_probe.py --speeds 3000000` (raw HCI Reset, 4 bytes only) with power-enable (`0x0402 = 0x0b`) and BT_WAKE (pin 164 high) asserted by `boot/bt_wake_experiment.py` (self-restoring; the user runs it). A DT clock change needs a kernel build.

## Constraints
No hardware access (the user runs hardware tests). No downloads without asking the user. Never commit firmware, NVRAM, calibration, OTP, ROM/RAM dumps, MACs, device identifiers, Ghidra projects, session transcripts or raw ADT/FDT. Use `/opt/homebrew/bin/python3`, `command ls` (ls is aliased), no stdin-heredoc python.
Commit each note with a path-limited commit and the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. If a Nix store path or Ghidra project is missing, ask the user before downloading or re-importing.

## Deliverables
1. The exact iOS register programming for 3 Mbaud on this UART (or a clear statement that iOS uses another mechanism and which).
2. The source of the baud clock and the smallest Linux change (DT/driver) to reproduce it.
3. A yes/no with evidence on any required 32.768 kHz clock for the Bluetooth module.
4. Anything in the above that contradicts our measurements or the hypothesis (e.g. if iOS actually autobauds from 115,200, say so and where).
