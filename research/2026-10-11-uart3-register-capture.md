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
