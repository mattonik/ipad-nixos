# Touch ROM status `4c b1`: static analysis (2026-10-12)

Static only: Ghidra decompile of `AppleMultitouchSPI` (MultitouchSoftware-275.27, `0xffffff8002fb7000`..`0xffffff8002fd0000`) in the iPad5,3 12B410 kernelcache (base `0xffffff8002593000`), plus an offline structural check of the exported packet (verdicts and lengths only). No hardware, no downloads. Labels: **E** read in code or computed, **I** inference, **U** unknown.

## Short answers

1. **`4c b1` is not interpreted anywhere in Apple's driver (E).** Every reader of the 2-byte ATN/ACK reply tests only `4b c1` (data, `0xfc43c4`, `0xfc4560`, `0xfc484c`, `0xfc4b94`) or `4a d1` (register write, `0xfc22c4`). Any other value is "failure": the same packet plus query is resent, at most 5 times. There is no "continue", "busy" or "poll again" branch. Its meaning is **U**; best reading **I**: status n = 0xc in the same family, "not data-OK".
2. **No pre-firmware command is missing (E).** Between the detect frame and the firmware, Apple sends nothing. `bootloadDevice` (`0xfc3fb4`, slot `+0xc8`) does only `downloadMode(1)` (unsupported on J81), the firmware send, proximity cal, cal, `performCalibSeq`, execute. Ahead of every bootload attempt `0xfc1570` re-runs the HBPP detect (`0xfc1d10`), nothing else.
3. **The packet is structurally valid by Apple's own constructor rules (E, computed).** So the likeliest causes are wire-level (the Linux S5L transmit path) or a ROM state we do not know, not the packet content or a missing command.

## 1. Status words (Q1)

| Word | n | Where compared | Meaning |
|---|---|---|---|
| `18 e1` | | detect accept set (`0xfc1d10`); also the DATA frame header and filler word | echo/idle-class (E for use, meaning I) |
| `1a a1` | | detect accept set; ATN header (`0xfc1fc0`) | same |
| `1f 01` | | detect accept set; also the calibration request word | ROM idle word (E from hardware run 7) |
| `48 79`, `49 69` | 8, 9 | detect accept set only | accepted as "in HBPP"; no code names them (U) |
| `4a d1` | 0xa | `0xfc22c4` register write must read it | register write OK (E) |
| `4b c1` | 0xb | every DATA chunk send | data packet OK (E) |
| `4c b1` | 0xc | **nowhere** | unknown, treated as failure (E) |

Detect (`0xfc1d10`) succeeds only if reply words 0 and 1 are both in `{18e1,1aa1,1f01,4879,4969,4ad1,4bc1}`. `4cb1` is not in that set either.
Invariant (computed over all five 4x words): the four nibbles sum to 0x1c, with the second and third nibbles summing to 15 (n=8,9) or 23 (n=a,b,c). So `4c b1` is a well-formed status of the same family, not line noise (E arithmetic, I meaning). If codes are numbered by event, 8, 9, a (reg), b (data), c is the next event class; "checksum or length error" is only one candidate (U). Strings in the driver name no ROM status.

## 2. What the ROM sees in a data packet (Q2)

Format built by `0xfc5690` (E), after the 2-byte frame header `18 e1`:

| Offset | Field |
|---|---|
| 0-1 | `30 01` data command |
| 2-3 | payload length in 32-bit words, big-endian |
| 4-7 | destination address, 16-bit halves swapped |
| 8-9 | big-endian 16-bit byte sum of bytes 2..7 |
| 10.. | payload, each source 16-bit pair byte-swapped |
| end | 32-bit byte sum of the payload, halves swapped (4 bytes) |

Overhead 16 bytes, so unconstructed chunk length is payload+16 (E). Chunk limits: firmware path up to 0xfff0 payload (`0xfc4560`), calibration and prox 0x3f0 (`0xfc484c`, `0xfc4b94`). Payload length must be a multiple of 4. Destination for unconstructed firmware is the byte offset from 0.

**Constructed Firmware vs this format (E, computed offline):** the 59,288-byte property parses as exactly ONE packet consuming all bytes: header ok, command ok, 14,818 words (59,272 payload, below 0xfff0), header sum ok, payload sum ok, destination 0 (same as Apple's unconstructed firmware). The driver adds nothing: the constructed path sends the bytes verbatim, transmit-only, length unrounded when PIO and `(len+3)&~3` when DMA (already aligned). No length prefix, no byte-swap, no address-setup command (E: `0xfc43c4`). Addresses 0x10001c04/0x10001800 etc. are only for calibration downloads.

## 3. Single-transfer implication (Q3)

Apple itself sends this packet as one transfer and one query, so chunking is not required (E). Retry branches: only "resend whole pair", up to 5 (E). On total failure `bootloadDevice` returns 0, `IOSleep(40)`, and the owner (`0xfb8f88`) repeats the whole attempt (detect again + bootload) up to 3 times, no reset (E).
What differs from Apple is the transmit path (I): the S5L PIO/FIFO code in `spi-apple.c` was broken until 2026-10-12 and receive is still broken above 32 bytes; transmit-only is "working" but byte integrity on the wire for 59 KB has never been verified (no RX loopback possible). A dropped, repeated or shifted byte anywhere would yield a payload-sum error. The header (first 12 bytes) is what the ROM validates first, so a deterministic reply identical across clocks and delays is slightly more consistent with a ROM-side or header-level cause, but a systematic driver artifact (e.g. FIFO refill pattern independent of clock) is not excluded (U).

## 4. ROM state afterwards (Q4)

Detect is stateless 16-byte frame Apple repeats before every attempt (E), and hardware run 8-9 showed the ROM still answers `1f 01` on idle frames. No documented command resets a download except the reset line (E: `0xfc0b58` path). Recovery = reset assert/release and repeat power order (I). Whether the ROM still answers detect after `4c b1` has not been tested (U).

## 5. Change list for the next hardware run (`boot/touch-diag.c`, `boot/touch_fw_packets.py`)

Each step adds one variable; stop at first `4b c1`.
1. **After `4c b1`, probe stickiness:** repeat `1a a1` 3 times at 0/1/10 ms (no resend) and print each; then send the long ATN (8 bytes: `1a a1 18 e1 18 e1 18 e1`, status in rx bytes 2-5, as Apple does for MemRead) and log it. Then re-send the 16-byte detect frame and record whether `1f 01` returns (answers Q4).
2. **Small clean packet first:** add `touch_fw_packets.py --rebuild N` that re-creates Apple's DATA packet (format in section 2) from the verified payload with a given chunk size; send a 64-byte-payload packet (80 bytes, PIO, below the FIFO-trouble region), query `1a a1`. Expect `4b c1`. If this works, ramp payload 256, 1008 (0x3f0), 4096, 16384, 59272 (one packet each, reset between) to find the size where `4c b1` appears; that separates wire corruption from ROM semantics. Overwriting RAM at address 0 is volatile.
3. **Chunked rebuild:** if the full size is the only failure, send the payload as 0x3f0-byte packets with increasing offsets as destination, one `1a a1` per packet requiring `4b c1` (Apple's unconstructed pattern). Do not feed the constructed bytes unchanged in this mode.
4. **Full Apple order per attempt:** detect frame immediately before each bootload attempt, 40 ms sleep between failed attempts, max 3 attempts; keep 5 pair retries inside an attempt.
5. **Wire check (no hardware change):** time and log the transfer, and add a kernel-side check for `spi-apple.c` underrun/refill counters if available; capture dmesg for the transfer.
6. **Host test:** add `test_touch_fw_packets.py` cases for the structure parser (section 2) using a synthetic packet, so `--rebuild` and the validator are covered.
Not recommended: pre-commands (none exist), `function-enable_download` (absent), more clock/delay variation (already shown invariant).
