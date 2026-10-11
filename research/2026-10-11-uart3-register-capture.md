# UART3/UART5 register capture (read-only), 2026-10-11

Tool: `uartpeek` (static, `/dev/mem`, `O_RDONLY`, only UART3 `0x20a0cc000` and UART5 `0x20a0d4000`; flake package `uartpeek-static`, `boot/uartpeek.c`, contract test `boot/test_uartpeek_contract.py`). Running payload P4; no register was written.

| offset | UART3 (Bluetooth, `ttySAC1`; last Linux request 3,000,000 baud) | UART5 (battery HDQ, `ttySAC2`) |
|---|---|---|
| +0x00 ULCON | 0x00000003 (8 bit) | 0x00000007 (8 bit, 2 stop bits) |
| +0x04 UCON | 0x00000085 | 0x00001885 |
| +0x08 UFCON | 0x00000031 | 0x00000031 |
| +0x0c UMCON | 0x00000001 | 0x00000001 |
| +0x10 UTRSTAT | 0x00000006 | 0x00000046 |
| +0x24 | 0x00000000 | 0x000000fe |
| **+0x28** | **0x00000000** | **0x00000019** |
| **+0x34** | **0x00000000** | **0x00000000** |
| **+0x38** | **0x00000000** | **0x00000000** |
| +0x3c | 0x00010005 | 0x00010005 |

Reading: Linux's legacy path left UART3 with `+0x28 = 0` for the 3,000,000 request (`(24e6 + 8*3e6)/(16*3e6) - 1 = 0`, i.e. 1.5 Mbaud, the measured ~1.47 M) and the two Apple baud registers `+0x34`/`+0x38` at 0 (the power-on/legacy state; Linux never writes them).
UART5 holds `0x19` (25): Linux's legacy value for 57,600 baud. The agent's table gives the SAME number `0x19` for 115,200 in Apple's packed encoding, but with `+0x34 = +0x38 = 0x55555555`. So on this hardware `0x19` can mean 57.6k (pattern 0) or 115.2k (pattern 0x55555555):
the pattern registers change what the divider means, which the static reconstruction alone cannot settle. Empirical test: `boot/uart3_baud_experiment.py` (writes the candidate triples into UART3's three baud registers on the live iPad, times a drained transmit, restores the originals).

## Round 1 of the empirical test (run by the user, `boot/uart3_baud_experiment.py`, first version)

Method: write the candidate `+0x28/+0x34/+0x38` into UART3, hold the port open (so the tty layer does not reprogram it), `dd` N zero bytes, time with `/proc/uptime`, baud = N*10/seconds. Chip unpowered. Originals restored (verified).
Caveat found afterwards: with the port held open the last ~4 KB stays in the tty buffer undrained, so slow rows read too fast (tens of kbaud). High-rate rows are accurate to a few percent. Round 2 polls the UART's own transmitted-byte counter instead.

| candidate (`+0x28` / `+0x34` / `+0x38`) | measured | legacy model (nclk 24 MHz) |
|---|---|---|
| 0 / 0 / 0 (control) | 1,485,149 | 24e6/(16*1) = 1.5 M OK |
| 0 / 0x55555555 / 0x55555555 (agent's table "3 Mbaud") | **1,392,111** | 1.5 M x 15/16 = 1.406 M |
| 0x19 / 0x55555555 both (table "115,200") | ~60 k (~52 k corrected) | 57.7 k x 15/16 = 54 k |
| 0x19 / 0 / 0 (legacy 57.6 k) | ~74 k (~55 k corrected) | 57.7 k |
| 1 / 0x55555555 both (table "1.5 M") | 709,220 | 750 k x 15/16 = 703 k |
| 2 / 0 / 0 (table "921,600") | 506,329 | 24e6/(16*3) = 500 k |
| 0 / 0x55555555 / 0 | 1,408,451 (-5%) | |
| 0 / 0 / 0x55555555 | 1,470,588 (-1%) | |

**Conclusion:** in the current mode every row fits the legacy model `baud = 24 MHz / (16 * (UBRDIV + 1))`, slowed by the slot registers: `0x34` and `0x38` behave as fractional slot patterns that only slow the rate (both set to `0x55555555`: x 15/16). The agent's reading of `+0x28` as a "doubled" divisor
(`0x19` = 115,200, `0` = 3 M) is **not** what the hardware does with the power-on `+0x08` (UFCON = `0x31`). So the version-1 divider mode is selected by something the baud registers do not carry. Leading candidate: the FIFO/control word iOS writes first, `+0x08 = 0x1c1` (version 1) / `0xc1` (version 0), i.e. bit 8 (Linux has `0x31`). Round 2 tests this.

## Rounds 2 and 3 (run by the user) and a PMGR gate capture (read-only, by the assistant)

**Round 2** (true-drain timing via the UART's transmitted-byte counter): the FIFO/control word `+0x08` has no effect on the rate. Candidates `0x131`, `0x1c1`, `0xc1` all stayed legacy: `+0x28 = 0` -> ~1.49 M, `+0x28 = 1` -> 744 k, `+0x28 = 0x19` -> 57.4 k (legacy 24 MHz/(16*26) = 57.7 k). With `0x55555555` in both slot registers: -6 % (15/16).
**Round 3** (UCON): bits 8, 10, 11 (clock select 1, 2, 3, the Samsung CLKSEL field) and 15 change nothing: 28=0 -> 1.46-1.48 M, 28=1 -> 743-746 k in every case. (Interrupt-enable bits 9, 12, 13, 14 were deliberately not tested.)
**Conclusion:** the UART block's own registers (UCON, UFCON, +0x28, +0x34, +0x38) cannot raise the rate; in every combination it is 24 MHz / (16 x (+0x28 + 1)) minus the slot slowdown. The agent's table is consistent with a **48 MHz** input clock (`0x19` -> 48e6/(16*26) = 115.4 k, `1` -> 1.5 M, `0` -> 3 M, `2` -> 1.0 M), i.e. 2 x `nclk`:
whatever iOS does, the 3 Mbaud comes from a faster clock into the UART, not from a register mode inside it.

**PMGR clock-gate registers of the UARTs** (`uartpeek pmgr`, read-only window `0x20e020280..0x20e0202cf`; the UART ADT nodes all have `uart-version = 1`, identical `clock-ids = {0x115, 0x4}` and gates `0x50..0x58`):

| gate | UART | register (word 0; word 1 is 0 everywhere) |
|---|---|---|
| 0x50 | UART0 | 0x00000200 |
| 0x51 | UART1 | 0x000000ff |
| 0x52 | UART2 | 0x1f0000ff |
| 0x53 | UART3 (Bluetooth) | 0x1f0000ff |
| 0x54 | UART4 | 0x000000ff |
| 0x55 | UART5 (battery) | 0x1f0001ff |
| 0x56 | UART6 | 0x1f0002ff |
| 0x57 | UART7 | 0x000000ff |
| 0x58 | UART8 | 0x0f000300 |
| 0x59 | UART9 | 0x0f000300 |

Low byte `0xff` reads as power-state target/actual both ON (UART0 `0x200` is off). **Bits 9:8 differ per UART: 00 (UART2/3/4/7/1), 01 (UART5), 10 (UART6), 11 (UART8/9)**, and bits 28:24 vary (`0x1f` on the active ones, `0x0f` on UART8/9).
Whether bits 9:8 (or 28:24) are a clock mux/divider select, an instance index, or status is unknown; nothing has been written. A PMGR write is a new write category and would need the user's explicit approval.

## ADT clock table decode (static, by the assistant, 2026-10-11): the UART's baud clock is 24 MHz
The `arm-io,t7001` node carries `clock-frequencies`, a 96-entry table of little-endian 32-bit frequencies indexed by clock id (entries 0, 1, 3 = 24 MHz, 2 = 798 MHz, 4 = 100 MHz, 17 = 48 MHz, 21 = 24 MHz, ...).
The UART nodes' `clock-ids = {0x115, 0x4}`: low byte 0x15 = index 21 = **24,000,000 Hz** (the functional/baud clock, "nclk") and index 4 = **100,000,000 Hz** (the peripheral clock). `nclk-div` (value 1) is a property of the `dwi` display-interface node, not of the UARTs.
So iOS's `nclk` for UART3 is the same 24 MHz we measure; the clock is not the missing piece, contrary to the "48 MHz input" reading of the worked table. Instead the table's register values (`0x19` = 115,200, `1` = 1.5 M, `0` = 3 M at 24 MHz) fit
`baud = 24 MHz / (8 x (+0x28 + 1))`, a divide-by-8 base mode (with the 14/15/16 "factor" refinement), whereas the power-on mode (and every register combination tested in rounds 1-3: UCON bits 8/10/11/15, UFCON 0x131/0x1c1/0xc1, `+0x34`/`+0x38`) is divide-by-16.
The switch for the /8 mode is therefore a bit or field that the baud routine does not write and we have not toggled: candidates are ULCON (+0x00; Linux sets 0x03) and the UCON bits the line-control/interrupt routines own (notably 3, 5, 6 and the upper half), tested only partially so far (not tested: UCON 3/5/6/9/12/13/14/16-31, ULCON 3..7).

## Round 4 (UCON bit 20, run by the user): the first switch that changes the rate
iOS sets UCON bit 20 (`0x00100000`) only when `uart-version != 0` (`research/2026-10-11-uart-oversample-bit.md`, `9eed16d`). `UCON = 0x100085`, slot words 0, true-drain timing:

| `+0x28` | legacy /16 rate | measured with bit 20 | ratio |
|---|---:|---:|---:|
| 0x19 | 57.7 k | 81.5 k | 1.41 |
| 0x0c | 115.4 k | 163.5 k | 1.42 |
| 0x01 | 750 k | 1.056 M | 1.41 |
| 0x00 | 1.5 M | 2.06 M | 1.37 |

Control (bit 20 off) 28=0: 1.478 M. So bit 20 is a real baud-mode switch, but with zero slot words the gain is **~sqrt(2)** (effective divider ~11.3 = 16/sqrt(2)), not the 2x of a clean divide-by-8 mode and not yet iOS's 3 M. iOS always writes computed slot words (`0x55555555` for the table's 115.2 k, 1.5 M and 3 M rows); in the legacy mode those words only slow the rate (x15/16),
so in the new mode they may supply the remaining correction. Round 5 applies iOS's complete register triples with bit 20 set.

## Round 5 (bit 20 + iOS slot words, run by the user)
With UCON `0x100085`: `28=0x19` + slots 5555/5555 -> 76.9 k (nominal 115.2 k); `28=1` + slots -> 997 k (nominal 1.5 M); `28=0` + slots -> 1.935 M (nominal 3.0 M); `28=2`, slots 0 -> 706 k (table: ~1.0 M); `28=0`, only `+0x34` -> 1.94 M, only `+0x38` -> 2.05 M.
Compared with round 4 (bit 20, zero slot words: 81.5 k / 1.056 M / 2.06 M) the slot words again only slow the rate by ~15/16 (0.94): they behave the same in both modes. **Bit 20's gain is a constant ~x1.41 on every row** (effective divider ~11.3 instead of 16), but iOS's table needs divider 8 (x2). Missing: another ~x1.41.
(Ambiguity: the gain is within 0.5-1 % of both sqrt(2) = 1.4142 and 10/7 = 1.4286; the ADT clock table has 342,857,142 Hz = 2.4 GHz/7, whose tenth, 34.29 MHz, is exactly 24 MHz x 10/7. Not resolved.)
Round 6 (committed tooling, to be run): bit 20 combined with UCON bits 10 and 17 (iOS's baseline `old | 0x405` and a helper at `0x2d76a58`) and UFCON `0x131`/`0x1c1`, all at `28=0x19`, plus the full combination at `28=0`.

## Rounds 6-9 and the true-baud discovery (run by the assistant on the live iPad at the user's request while they were away)

**Round 6** (bit 20 + UCON bits 10/17 + UFCON 0x131/0x1c1): no change beyond bit 20 itself. **Round 7** (bit 20 + each of UCON bits 3, 5, 6, 8, 10, 14-19, 21-31 alone; 4 = send break and 9/11/12/13 = interrupt enables were refused by the tool): identical 81.5-81.7 k everywhere.
Corrected with the control row's own -0.76 % timing bias, bit 20 gave x1.428 = 10/7.

**Frame-length experiment (`boot/uart3_frame_experiment.py`)**: time per byte vs frame length n = 7..12 (5N1 .. 8E2). Legacy mode: time per byte is linear in n, slope = 17.37 us/bit = **57,566 baud (nominal 57,692), overhead 0.05 bit-times**: the method is valid.
**With UCON bit 20 the time per byte is constant (122.5 us at `+0x28 = 0x19`, 9.45 us at 1, 4.9 us at 0) whatever the frame length**, i.e. a fixed ~7.07 bit-times per byte: bit 20 is NOT a baud switch (it changes the transmitter's behaviour, identity unknown); the 10/7 gain and all of rounds 4-7 are therefore not line-baud evidence.

**Round 8 (the real finding):** with UCON untouched, writing a non-zero UPPER HALF of `+0x28` changes the line rate by exactly `16 / (16 - i)`: i = 1: x1.067, 2: x1.14, 3: x1.229, 4: x1.332 (at div 25, 1 and 0).
**Round 9:** `+0x28 = (i << 16) | div` gives `baud = 24 MHz / ((16 - i) x (div + 1))` for i up to 12 (sampling factor 16 down to 4):

| `+0x28` | factor | div | measured | expected |
|---|---:|---:|---:|---:|
| 0x50019 | 11 | 25 | 83.0 k | 83.9 k |
| 0x80019 | 8 | 25 | 114.3 k | 115.4 k |
| 0xc0019 | 4 | 25 | 224.7 k | 230.8 k |
| 0x80003 | 8 | 3 | 739 k | 750 k |
| 0xa0003 | 6 | 3 | 980 k | 1.0 M |
| 0xc0003 | 4 | 3 | 1.456 M | 1.5 M |
| **0x80000** | **8** | **0** | **2.79 M** | **3.0 M** |
| 0xa0000 | 6 | 0 | 3.73 M | 4.0 M |
| 0xc0000 | 4 | 0 | 5.50 M | 6.0 M |

Rows at 3 M and above read ~7-8 % low (per-byte overhead at those speeds; the low-rate rows are accurate to ~1 %). So **a true 3 Mbaud is reachable with `+0x28 = 0x80000` (factor 8, divisor 0) on the existing 24 MHz clock, with UCON, UFCON and the slot registers untouched**: no PMGR change, no new clock.
This matches the agent's reconstruction in kind (the candidate index in the upper half of `+0x28`; factors 16/15/14 in version 1) but the hardware supports the whole range down to 4; `+0x34`/`+0x38` (slot words) only slow the rate by ~15/16 in either mode and are not needed. Linux patch outline: for the Apple S5L UART3, pick (factor f in 4..16, div d >= 0) minimising |24e6/(f x (d+1)) - baud| (ties: larger f), write `((16 - f) << 16) | d` to UBRDIV; opt in with a device-tree property on `serial3`.

**Bluetooth probe at true rates (`boot/bt_3m_probe.py`, run by the assistant; same approved registers as before: PMU 0x0402 0x09 -> 0x0b, AP GPIO 164 high, UART3 baud registers; all restored and verified each time, battery Charging/80 % cap):** with power-enable and BT_WAKE both asserted and a raw HCI Reset (`01 03 0c 00`):
3,000,000 (`0x80000`), 2,000,000 (`0x40000`), 4,000,000 (`0xa0000`), 1,500,000, 923 k (`0x30001`), 750 k and 115,200 baud, each with and without RTS/CTS flow control, and frame formats 8N1, 8E1, 8O1, 8N2 at 3 M, 1.5 M and 115.2 k: **0 bytes received in every case**.
So the controller stays silent even at the exact rate iOS uses (3 Mbaud, the ADT `transport-speed`), so a baud-rate mismatch is not the cause. (The earlier suspicion that transport-encoding 3 might mean a parity/stop-bit variant is also not supported: 8E1/8O1/8N2 are silent too.)

**UART pad check (read-only):** the pads follow TX, RX, RTS, CTS in sequence for UARTs 1, 2, 4 (RTS = TX + 2; UART3's ADT pins are split: TX 14, RTS 32, so RX 15, CTS 33 by the same pattern). UART3's RX/CTS pads (15, 33) read `0x00070221` = peripheral function 1 with input enabled, identical to the working console UART0's RX/CTS (129, 131) and to UART4's (77, 79): the receive pads look correctly configured.

**Remaining hypotheses for the silent controller:** a missing 32.768 kHz low-power clock for the Bluetooth core (the agent found no iOS enable path); a power-up reset/timing requirement (`BT_REG_ON` low long enough then high, with the Wi-Fi side in a particular state); the PMU GPIO6 input that follows the power-enable write (`0x0063` bit 6, appears to be a power-good or related status); and a Wi-Fi-firmware-side dependency (BT core enabled through the chip's own registers, e.g. coexistence handshake). None tested yet.

**Power-up listen test (`boot/bt_powerup_listen.py`, run by the assistant; approved writes only, all restored: `0x0402 = 0x09`, pin 164 `0x00072602`, battery Charging):** with the port already open and a reader running (nothing transmitted), BT_WAKE and power-enable were asserted and the line watched for 4 s at 115,200, 3,000,000, 1,500,000 and ~923 k baud, power-cycling between rates: **0 bytes during power-up and after power-down at every rate**.
The controller does not announce itself on power-up either. Combined with the silent HCI Reset at every rate and frame format, the Bluetooth UART never receives a single byte from the chip.
ADT check: the PMU GPIO controller's consumers are `oscar` (pin 0, reset), `bluetooth` (pin 2, power_enable), `wlan` (pin 3, reg_on), the two hall-effect buttons (pins 10, 12) and `displayport` (pin 17, lcd_ldo); there is no second Bluetooth control pin.

## ChipCommon GPIO watch on a held diagnostic Wi-Fi boot (payload Q1; commit `71dbb0d`, parser fix after)
Payload `wifi-diag-Q1-chipgpio-...` (H1B diagnostic base, `brcmfmac.h1b_hold=1`), run by the assistant with the approved writes (PMU `0x0402`, AP GPIO 164), all restored and verified (`0x0402 = 0x09`, pin 164 `0x00072602`, `0x0010 = 0x00`). Read-only query `core cc 0x58 24` (the driver's safe ChipCommon GPIO block), result lines `cc <addr>: <words>`.
(First run: my parser took the address column as register values and compared only four registers; fixed and re-run, test added.) Corrected, all six registers, six snapshots (baseline twice, BT_WAKE high, BT_WAKE + power-enable at +0.2 s, +2 s, +6 s, after restore):
`gpiopullup 0x58 = 0`, `gpiopulldown 0x5c = 2`, `gpioin 0x60 = 0x290e`, `gpioout 0x64 = 0`, `gpioouten 0x68 = 1`, `gpiocontrol 0x6c = 0` in every snapshot: **no change at all.**
So the combo chip's own GPIO block does not see BT_WAKE or the power-enable (in particular chip GPIO 2, the NVRAM's `uart_wake_gpio`, stays at input 1; it is not wired to AP GPIO 164 or driven by them), and asserting them does not change any chip GPIO state.
This closes the last read-only software/diagnostic test from the agent's note (`research/2026-10-11-bluetooth-lpo-wifi-dependency.md`). What remains are hardware timing/reset experiments and electrical questions (a 32.768 kHz LPO, UART pad levels) that cannot be answered without measurement hardware.
