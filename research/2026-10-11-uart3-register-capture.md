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
