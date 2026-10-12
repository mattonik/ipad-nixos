# Touch ROM status words and the size dependence: static analysis (2026-10-12)

Static only: Ghidra decompile of `AppleMultitouchSPI` (`0xffffff8002fb7000`), `AppleSamsungSPI` (`0xffffff8002900000`) and `AppleSmartIO` (`0xffffff8002ff0000`) in the iPad5,3 12B410 kernelcache (`__PRELINK_TEXT` base `0xffffff8002593000`), plus the captured J81 ADT text for the `spi3` node (properties only). No hardware, no downloads. The touch ROM itself is not in the kernelcache, so anything about its internals is inference. Labels: **E** read in code or data, **I** inference, **U** unknown. Evidence is addresses and short constants only.

## Short answers

1. **The status words are one family, but Apple's code gives them no names (E).** The only consumers are the accept set in HBPP detect (`0xfc1d10`), `4bc1` after every data packet (`0xfc43c4`, `0xfc4560`, `0xfc484c`) and `4ad1` after a register write (`0xfc22c4`). No string, log or branch names ready/busy/overflow/crc/timeout for any of them (E: string sweep of the whole driver range). Table below.
2. **Nothing in Apple's code explains the 4 KiB / 8 KiB / 18 KiB thresholds (E), and Apple never sends a ROM-stage data packet that small AND early (see 3).** Best-supported reading: the ROM is not parsing our header at all and reacts only to the length of the chip-select frame (ranked hypotheses, section 3). The single most useful new fact: **Apple itself sends 1,040-byte calibration packets and arbitrary-size tail chunks to the same ROM before EXECUTE** (E), so "the ROM ignores small packets" cannot be a ROM rule; it points at what we put on the wire.
3. **Wire form matches Apple in bit width, mode, bit order, framing (E), with two differences:** the chip select (Apple drives a GPIO function, we use the pad's SPI function) and the DMA engine (Apple moves packets of 0x100 bytes and more through the SmartIO coprocessor; we poll the FIFO). Details in section 4.
4. **Correction to a note:** `2026-10-11-touch-no-ack-analysis.md` says the SPI3 node's `function-spi_cs0` is the ADT null function. It is not: the `null` one belongs to `spi2`; `spi3`'s `function-spi_cs0` is `OIPG` pin 51 (`0x33`), and the node has no `internal-cs` property (E, ADT text). The pad is the same one Linux muxes to function 1.

## 1. State table (answers Q1)

Reply words are read big-endian from the 2-byte full-duplex ATN query `1a a1` (`0xfc1fc0`, vtable slot `+0x898`), or from reply bytes 0-3 of the 16-byte detect frame.

| Word | n | Produced when | Consumed where | Label | Reading |
|---|---|---|---|---|---|
| `18 e1` | | frame header of a DATA packet and the filler word of detect | detect accept set | E use / I meaning | frame-type word, also tolerated as a reply |
| `1a a1` | | ATN query word, first word of the detect frame | detect accept set | E / I | same |
| `1f 01` | | ROM idle (our runs 7-21); also the calibration-request opcode word | detect accept set | E use / I meaning | "nothing pending / not addressed" |
| `48 79` | 8 | never seen on hardware | detect accept set only | E use / **U** meaning | tolerated status, no consumer |
| `49 69` | 9 | our frames of about 8 KiB to 17 KiB | detect accept set only | E use / **U** meaning | tolerated status |
| `4a d1` | a | after a 16-byte register-write frame | must equal it at `0xfc22c4` | E | register write OK |
| `4b c1` | b | after a data packet | must equal it at `0xfc43c4`/`0xfc4560`/`0xfc484c`/`0xfc4b94` | E | data OK; the only success for firmware |
| `4c b1` | c | our frames of about 18 KiB and more | **nowhere** | E (absent) / U meaning | not in the accept set; treated as failure |

Structure (E arithmetic): the four nibbles sum to 28 in all five 4x words; the last nibble is 9 for n=8,9 and 1 for n=a,b,c. Same family, so `4cb1` is a well-formed status, not line noise.

**What the accept set tells us (E code, I conclusion).** Apple re-runs the detect (`0xfc1d10`) before every bootload attempt (`0xfc1570`), and a failed detect powers the device off and gives up ("Could not detect HBPP", `0xfc85bf` string). So the set `{18e1, 1aa1, 1f01, 4879, 4969, 4ad1, 4bc1}` is exactly the words Apple's authors expected the ROM to still show at a retry: idle, the two ACKs, and **4879/4969 as non-fatal leftovers of a previous attempt**. `4cb1` is deliberately absent. Reading (I): 8 and 9 are benign/transient states, a and b are ACKs, **c is a fatal class** that Apple never expected to see and would not retry from. This is consistent with "the same word every time until reset" in our runs. Whether the ROM still answers detect after `4cb1` is untested (U).

Status is also latched (E from hardware): the reply to a query does not depend on the query's own content, so it behaves like a status register preloaded into the slave's transmit shift register, updated at the end of a frame the ROM recognised.

Other strings that name states belong to different classes (E): `MTSPIBootloader` "Sending CHECK packet ... getting RESULT" and `MTSPIBootloader_TwoStage` "stage 1 / stage 2 ... b speed firmware packet" are the pre-Z2 bootloaders. J81 is `MTSPIBootloader_Z2`/N1 (E, personality `IOClass`), which uses none of that.

## 2. What Apple sends the ROM, and in what shape (answers Q2 first half, Q3, Q4)

Order inside `bootloadDevice` (`0xfc3fb4`), E: firmware (constructed 59,288-byte packet, or unconstructed chunks), proximity calibration, calibration, `performCalibSeq`, **EXECUTE last**. Nothing runs from RAM before EXECUTE, so every one of these packets is received by the ROM.

| Packet | Size on the wire | Path | Destination | Reply required |
|---|---|---|---|---|
| firmware, constructed | 59,288 | one transfer; DMA when the flag is set and size >= 0x100 | 0 | `4bc1` |
| firmware, unconstructed | up to 0xfff0 payload + 16 = 0x10000 per chunk, tail chunk any multiple of 4 | same, loop with offset as destination (`0xfc4560`) | running byte offset | `4bc1` per chunk |
| proximity calibration, calibration | 0x3f0 payload + 16 = 1,040 per chunk, tail chunk any multiple of 4 (`0xfc484c`, DMA length `(payload+0x13)&0x1fffc`) | same | calibration address (cal-dl-addr, prox-cal-addr personality values) | `4bc1` per chunk |

Consequences:

- **E: the ROM is exercised by data packets of 1,040 bytes and by arbitrary tail sizes, before the firmware executes.** A ROM that ignores every complete packet of up to 4 KiB would break Apple's own flow. Therefore the idle replies to our 80, 272, 1,024 and 4,112 byte packets are not ROM behaviour for a correct frame (I).
- **E:** the `0xfff0` limit is Apple's own buffer: the unconstructed path allocates a 0x10000-byte buffer (`0xfc4560`, `inTaskWithOptions`-style call with capacity `0x10000`, alignment `0x1000`). It is not a statement about the ROM's receive buffer. The real ROM receive size is **U** and not recoverable from any driver code.
- **E:** a data packet is always ONE transfer, ONE chip-select interval, then a separate 2-byte ATN query. Nothing is sent between the detect and the first data packet (previous note, still holds). `function-enable_download` is absent on J81 (no-op).
- **Which packets could a small-packet idle depend on (Q3, I):** the only things Apple's small packets have that ours lack are a **non-zero destination** (calibration addresses) and the preceding accepted firmware. Our rebuilt small packets use destination 0 (the firmware's own destination). It is possible, not shown (U), that the ROM treats a destination-0 write as the image start and wants a full image there. Cheap to test (change list, step 5).

## 3. Why 4 KiB / 8 KiB / 18 KiB? Ranked hypotheses (answers Q2)

Hardware facts (from the brief): idle up to 4,112; `4969` from 8,208 to 17,424; `4cb1` from 18,448 to 59,288; nothing changed with clock (0.5-4 MHz requested, only tested on the full packet), word delay, chunking with pauses (only tested on the full packet), power order. Bracketing, 16 bytes above round numbers: T1 in (4,112, 8,208], T2 in (17,424, 18,448]. The two tested points just above the thresholds are exactly 8,192+16 and 18,432+16, so thresholds at 8 KiB and 18 KiB (0x4800) are as consistent as anything else.

**H1 (best): the ROM never parses our header; it reacts only to frame length (I).** Evidence: the reply is the same for any content of a given size (rebuilt payload slices, chunk patterns), the 16/32-byte frames the ROM does understand work, and Apple's own small packets prove a correctly framed small packet would be ACKed. A slave that finds no valid command can still report the size class of the junk frame (fits / too long / overruns its receive area), which gives size-only dependence with no ACK. Under H1 the thresholds are ROM receive-area sizes (U: about 8 KiB and about 18 KiB; the second not a power of two, so possibly two areas, or a DMA block plus header). Why the header would not be recognised is the open part: candidates are a leading-byte problem in our tx-only PIO path (first bytes lost or shifted), or a ROM precondition we do not know. Cheap to confirm or kill with content-independence tests (change list, steps 1-3).

**H2: elapsed chip-select time, not bytes (I, new, untested).** At the measured 1.74 us/byte (requested 1.984 MHz, no word delay) the thresholds are T1 in (7.2, 14.3] ms and T2 in (30.3, 32.1] ms. 256 and 1,024 ticks of the 32.768 kHz clock the host supplies (KLCT) are 7.8 ms and 31.25 ms, both inside the brackets, and 8 ms / 32 ms round numbers also fit. The clock runs the touch chip's own timers (E: personality `clk32-clock-enable`, `fll-mval`). The data cannot exclude this because boundaries were measured at one clock only, and the "unchanged by clock/pauses" results were taken on the full packet, which is above both thresholds at every setting. Weakness: Apple's own transfer takes about 350 ms (59 KB at about 8 MHz plus 5 us word delay, I from the config constants) and ends in `4bc1`, so time alone cannot be the whole story; it would need to be one input of a header-validity check. Rank 2 because it is the one hypothesis where a single cheap run decides it.

**H3: wire corruption in our transmit-only PIO path (I).** `spi-apple.c` PIO transmit-only was broken until today (patch 0098) and its byte integrity on the wire has never been checked. A size-dependent error pattern (for example a periodic FIFO refill glitch or a lost word at each refill) would corrupt larger packets differently and would not be affected by clock or pauses. It does not obviously explain deterministic thresholds, hence rank 3, but it is the only cause that also explains why our small packets fail while Apple's succeed, and the controller difference in section 4 is real.

**H4: ROM RX rate overrun against a slower consumer (I, weak).** Would make the failing size depend on host byte rate. Contradicted by the clock sweep on the full packet (a 0.5 MHz run was slower than Apple's effective rate and still failed) and does not explain small-packet idle. Keep only as a footnote.

**What Apple's DMA path adds (E, Q2 third part).** Packets of 0x100 bytes or more go through `AppleSamsungSPIController` transfer (`0xffffff8002900f64`) with a tx memory descriptor: the controller sets CFG mode DMA (bit 6), TXCNT/RXCNT to the full length, and hands **one** DMA command for the whole length to the SIO DMA channel (`vtable +0xe0`). The channel is `AppleSmartIODMA` (`0xffffff8002ff9122` class): the command is turned into a physical page list (`length/pagesize + 2` entries, up to 0xaaa entries of 12 bytes) and submitted as a message to the **SmartIO coprocessor** (`0xffffff8002ff3f28`); the coprocessor firmware feeds the SPI FIFO. The FIFO depth is configurable (`validFIFODepth`, `0xffffff8002ff4d40`) and the SPI3 node's `dma-channels` carries two entries with parameters 0x80 and 0x40 (E, ADT). **No host-visible per-descriptor pause, ATN or IRQ handshake exists** (E): the host driver neither waits for the ROM between pieces nor reads the interrupt line in the whole bootload (previous note). What SmartIO firmware does between pages is **U**. The 59 KB constructed packet is therefore one SPI transaction as far as the wire is concerned; pauses or handshakes would have to come from the SmartIO core, not from a fixed per-descriptor rule (U).

## 4. Wire form (answers Q4)

All E, from the controller config routine (`0xffffff8002900e10`), validator (`0xffffff8002900cf8`), start (`0xffffff8002900738`), and the `spi3` node:

- **Bits per word:** fixed per device from `reg` byte 11 = 8, validated to 8/16/32; there is **no per-transfer override** (the optional command struct only carries three delay words, NULL for firmware). So data packets are 8-bit words, LSB-first (byte 10 = 1 leaves the S5L MSB-first bit clear), mode 0 (bytes 8, 9 = 0). Our 8-bit LSB-first mode 0 is the same. No 16/32-bit data transfers exist in this driver.
- **Word delay and hold:** register `0x38` = ceil(5000 ns x pclk), CS setup/hold 10 us before the first clock and after the last (`+0x184`), SCK divider ceil(124 ns x nclk) with a minimum of 2 only on spi-version 0. J81 `spi-version` is 1.
- **Chip select:** `spi3` has no `internal-cs`, so the transfer calls `function-spi_cs0` with 1 before and 0 after the frame (`OIPG` pin 51, args `01 00 01 00`), 10 us each side. The frame is exactly one CS interval for any length. Linux muxes pin 51 to the SPI function and lets the controller drive it. Equivalent as long as the controller holds CS steady for the whole transfer; unverified for the polled transmit-only case (U).
- **Counts:** for transmit-only Apple writes RXCNT = 0 and TXCNT = length (E, same as Linux).
- **Our measured clock error matters for the delay:** the SPI source clock in our DT is about 2.3x too low (requested 5 us word delay measured as about 2 us per byte, requested 1.984 MHz about 4.5 MHz). Apple's real wire is about 8 MHz SCK with a true 5 us gap per byte, roughly 6 us per byte. To reproduce it, request about 11 us of word delay and about 3.5 MHz (I, scaled by 2.3).
- **PIO below 0x100:** Apple refills 16 bytes per IRQ in mode IRQ (CFG bit 5, thresholds 0x180). Not a wire difference.

## 5. Change list for the next hardware run (`boot/touch-diag.c`, `boot/touch_fw_rebuild.py`)

Every run is a fresh power-up, Apple's order, mode 0, LSB-first, detect frame first, transmit-only, one `1a a1` afterwards, all as in the 2026-10-12 runs. Steps are ordered by information per run; steps 1-4 need no new firmware bytes beyond rewrapping the verified payload. All new packets stay in the volatile ROM RAM; reset recovers.

1. **Content independence (kills or confirms H1).** Send a frame of exactly 8,208 bytes and one of 18,448 bytes with the 12-byte header replaced by zeros and payload zero-filled (`--raw-fill 0x00`); then the same with the valid header and a deliberately wrong header sum (flip the sum, recompute nothing). Prediction under H1: same replies as the valid packets (`4969`, `4cb1`). If any variant differs, the ROM does parse the header, and the difference says which field it checks.
2. **Declared vs clocked length.** (a) 80 clocked bytes whose header declares 14,818 words (valid header sum for that length, truncated body). (b) 59,288 clocked bytes whose header declares 16 words (sum recomputed). Under H1 (a) is idle and (b) is `4cb1`; if the reply follows the declared length instead, the ROM is reading the header.
3. **Time vs bytes (decides H2).** Use options that already exist: a 4,112-byte packet at `--spi-hz 500000` (about 26 ms, in the predicted `4969` band if time matters, idle if bytes matter), and the same packet in 1 KiB chunks with `--chunk-delay-us 2000` (about 15 ms). Then bisect T1 and T2 at two clocks (for example 4,608 / 6,144 / 17,920 at 1.984 MHz and at 4 MHz); thresholds that move with the clock mean H2.
4. **Wire check without hardware change: full-duplex pieces.** Send the 8,208-byte packet as one message of 16-byte (or 32-byte, the working rx limit) full-duplex transfers with chip select held (`cs_change = 0` between pieces) and log every received byte. This exercises the path that is known to work for 16-byte frames and shows what the ROM presents on MISO during a data frame. Print only decoded 16-bit words, no raw dumps. If the ROM answers a valid frame differently, header acceptance is visible in-band.
5. **Destination and size.** A 1,040-byte packet (1,024 payload) with non-zero destination (for example 0x400, inside the firmware RAM, and separately the personality's cal-dl-addr 0x10001800) taken from the verified payload. Apple's calibration packets have exactly this shape, so `4bc1` here would prove the sending path and expose a ROM rule about destination 0. If idle again, the problem is wire-level (H3) rather than semantic.
6. **Apple's real timing.** Full 59,288-byte packet with word delay about 11 us and `--spi-hz 3500000` (real roughly 5 us gap, 8 MHz clock), then with the chunk path off. The earlier "5 us" runs applied only about 2 us.
7. **Do not add (static evidence against):** pre-commands, a "start download" word, a size announcement, `function-enable_download`, 16/32-bit word transfers, reordered power, IRQ waits. Not worth a run before 1-5: more clock/delay sweeps of the full packet (already shown invariant above T2).
8. **Later, only if 1-5 point at chip select:** emulate Apple's GPIO chip select (DT `cs-gpios` on pin 51 with the pad left as GPIO) so CS cannot move under the controller. Needs a kernel rebuild; deferred.

## 6. Verification pointers

- Status consumers and accept set: `0xffffff8002fc1d10` (binary-search compare against `18e1 1aa1 1f01 4879 4969 4ad1 4bc1`), `0xffffff8002fc43c4` (`4bc1`), `0xffffff8002fc22c4` (`4ad1`).
- Chunk buffer and limits: `0xffffff8002fc4560` (capacity `0x10000`, chunk `0xfff0`, DMA length `(payload+0x13)&0x1fffc`), `0xffffff8002fc484c` (0x3f0).
- Bootload order with EXECUTE last: `0xffffff8002fc3fb4`.
- SPI config and CS: `0xffffff8002900e10`, `0xffffff8002900cf8`, `0xffffff8002900738` (`internal-cs`, `spi-version`), transfer `0xffffff8002900f64`.
- SmartIO DMA: submit `0xffffff8002ff3f28`, FIFO depth helper `0xffffff8002ff4d40`.

## Hardware follow-up, 2026-10-12 (items 3 and 6 of the change list; valid packets only, within the standing approval)

- **Time vs bytes (hypothesis 2) is refuted.** At a requested 500 kHz (6.4 us/byte) the 1,024-byte packet (6.6 ms on the wire) and the 4,112-byte packet (26.3 ms; also chunked 1 KiB with 2 ms pauses, 36 ms) still return the idle `1f 01`, while the 8,208-byte packet (52.5 ms) returns `49 69`, exactly as at the fast clock where the same 4,112-byte packet lasted 7 ms and the 8,208-byte one 14 ms. A 26 ms transfer is idle but a 14 ms transfer is not, so the first threshold follows the byte count (between 4,112 and 8,208 bytes), not elapsed chip-select time.
- **Apple's real wire timing (item 6)**: the full packet at a requested 3.5 MHz with an 11 us word delay (316 ms, 5.33 us/byte) still returns `4c b1`.
- Not run, needs approval (not valid-packet-from-payload tests): zeroed/invalid-header packets (item 1), declared-vs-clocked length mismatch (item 2), packets with destination 0x400 / 0x10001800 (item 5), full-duplex piecewise sends (item 4).
