# Touch firmware upload: first hardware result (2026-10-11)

Payload `m1n1-hoolock-wifi-touch` (clean production kernel, spidev child on SPI3 enabled, `spidev.bufsiz=65536`), run by `boot/touch_upload_experiment.py --go` after the dry run and the user's explicit approval.

Sequence (from `touch-diag`): reset asserted, touch clock enabled, LDO14 on, GPIO95 high, dummy SPI frame (all-zero reply), reset released, boot IRQ falling edge at ~0 ms, then ONE 59,288-byte full-duplex SPI message (mode 2, 1.984 MHz) with the constructed packet (header `18 e1`), then the 2-byte ATN/ACK query `1a a1`.

Result:
- The transfer completed without a spidev/SPI error (the 64 KiB buffer and single-message path work).
- ACK reply was `f0 01`, NOT the expected `4b c1`. `f0 01` is the same idle pattern the ROM returned to every earlier frame (research/j81-touch-diagnostic.md). The tool aborted without retry, as designed.
- The unwind restored everything: reset asserted, GPIO95 low, LDO14 back to 0x00, touch clock disabled (register 0x800002dc, bit pattern as before apart from the status bits). No SPI timeout, no stuck IRQ, no error in the run.

What this does and does not show:
- The firmware packet was transmitted; the controller did not acknowledge it in the way Apple's N1 path requires. The ROM still looks idle after the transfer.
- Open possibilities (not tested): the ROM needs a handshake or wake sequence before the data packet (Apple may assert/observe the ATN/IRQ line between the packet and the query, i.e. the query must follow an IRQ edge, not a fixed gap); chip-select continuity or inter-byte clock pauses in the 59 KB message (the S5L PIO FIFO refill, see spec "U" items); a different SPI rate or mode for the bootloader; the reply is delayed and the ACK query must be repeated a few times (Apple retries the packet plus query up to five times).
- No evidence of any harm.

Next candidates (each needs a separate go-ahead): repeat the query a few times and watch the IRQ line after the transfer; try a slower rate (e.g. 500 kHz) or smaller messages only if the spec supports them; study how Apple waits for the IRQ between packet and query.

## Second run: repeat-query (same boot, same payload, user-run)

Same power-up and the same single 59,288-byte transfer (completed, no SPI error), then the `1a a1` query repeated six times on a 0/2/10/50/200/1000 ms schedule while the IRQ line was watched (packet not resent):

| query | wait | IRQ edges during wait | IRQ level | reply |
|---|---|---|---|---|
| 1 | 0 ms | 0 | 0 | `f0 01` |
| 2 | 2 ms | 1 | 0 | `f0 01` |
| 3 | 10 ms | 1 | 0 | `f0 01` |
| 4 | 50 ms | 1 | 0 | `f0 01` |
| 5 | 200 ms | 1 | 0 | `f0 01` |
| 6 | 1000 ms | 0 | 0 | `f0 01` |

Unwind clean again (clock register back to its pre-run value, LDO14 off, GPIO95 low).

Reading:
- The reply never changes: no delayed ACK, so "the ACK just comes late" is ruled out for up to ~1.3 s.
- The IRQ line sits low after the boot edge and a single edge shows during queries 2-5 (most likely each query pulses it, not a reaction to the packet; not proven).
- Together with the first run, the ROM answers the same idle pattern before and after the packet, as if the packet were never recognised as a firmware download.
- Remaining hypotheses: ROM needs a wake/handshake frame or specific ATN/IRQ timing before the data packet (the all-zero dummy reply suggests the first frames are not even clocked in); chip-select or clock breaks inside the 59 KB message (S5L PIO FIFO refill) corrupting it; different SPI mode or rate for the bootloader; or the data packet must be sent with the IRQ line in a specific state. Next experiments need a separate go-ahead.

## Third to fifth runs: slower rate and chunked transfers (same boot, user-approved)

Same power-up, same 59,288 bytes, same six-query repeat, each run unwound cleanly (LDO14 off, clock register restored):

| run | SPI rate | transfers (one message, CS held) | result |
|---|---|---|---|
| 3 | 500 kHz | 1 x 59,288 | six queries all `f0 01`, NOT acknowledged |
| 4 | 500 kHz | 58 x 1024 | six queries all `f0 01`, NOT acknowledged |
| 5 | 1.984 MHz | 116 x 512 | six queries all `f0 01`, NOT acknowledged |

Conclusion: neither a 4x slower clock nor shorter PIO runs inside one chip-select interval changes the ROM's reply, so FIFO-refill clock pauses in the SPI controller are very unlikely to be why the packet is not accepted. (Not excluded: chip-select breaks between transfers behaving differently than the core assumes; nothing was measured on the wire.) Remaining hypotheses: a wake/handshake or ATN/IRQ-timed step before the data packet, a different SPI mode for the bootloader, or the ROM requiring the constructed packet in a different framing than we send. Next step is evidence, not another blind variation: re-read the Apple driver path for the exact IRQ/ATN handling between reset release and the first packet.

## Sixth run: detect-only, LSB-first, mode 2, 1.984 MHz (after the Apple-driver analysis; no firmware sent)

Every reply is now a regular stream instead of the old `f8 80`/`f1 01` pattern: `0f 80 8f 80 8f 80 ...`. Read as a bit stream this is the ROM idle word `1f 01` repeated, delayed by exactly one bit (drop the first bit and it regroups into `1f 01 1f 01 ...`). So the bit-order diagnosis (research/2026-10-11-touch-no-ack-analysis.md) holds: the ROM answers with its valid idle word and our data lines up except for a one-bit shift, which points at the SPI clock phase/polarity (mode 2 here; Apple's decoded mode is 0). The detect check printed FAIL because of the shift; the handshake frames got the same shifted stream. No firmware was sent; unwind clean.
Next (needs a go-ahead): the same detect-only run with `--spi-mode 0`.

## Seventh run: detect-only, LSB-first, MODE 0, 1.984 MHz (user-approved, no firmware)

**First valid communication with the touch ROM.** Detect frame reply: `1f 01` x 8, both checked words known, `DETECT PASS`. The wake, short and long ATN frames all return `1f 01` as well. Mode 0 removed the one-bit shift seen in mode 2. The root cause of the whole "idle pattern" saga is confirmed: wrong SPI bit order (MSB-first) and mode. Unwind clean.
Next (needs a go-ahead): the firmware upload with `--spi-mode 0` (LSB-first default), expecting `4b c1`; the ACK query reply decoded with the same settings.

## Eighth run: firmware upload, LSB-first, mode 0, 1.984 MHz (user-approved)

Detect PASS (`1f 01` x 8). One 59,288-byte message (completed without error), then six `1a a1` queries over ~1.3 s: every reply `1f 01` (the idle word), never `4b c1`. Unwind clean. So the link is now valid, but the ROM does not take the packet as a firmware download.
Differences from Apple's recovered sequence still present (research/2026-10-11-touch-no-ack-analysis.md): (1) Apple's SPI clock is ~8 MHz with a 5 us inter-word delay and 10 us CS setup/hold; we send back-to-back bytes at 1.984 MHz with no word delay (the Linux S5L driver writes WORD_DELAY 0); (2) Apple sends the 2-byte wake `19 c1` first, power-before-clock with 5 ms/15 ms sleeps, and starts bootloadDevice >= 15 ms after the detect; we send the packet immediately after the detect; (3) Apple's firmware transfer is transmit-only (rx NULL), ours is full duplex; (4) the packet+query pair is retried by Apple up to five times (we only repeat the query). 

## Ninth run: Apple order + transmit-only packet + pair retries (`--apple`, mode 0, LSB-first, 1.984 MHz; user-approved)

Power order LDO14, GPIO95, 5 ms, clock, 15 ms, wake `19 c1` (reply `00 00`), 10 ms, dummy, reset release, detect PASS (`1f 01` x 8), 30 ms, then five packet+query pairs, each packet transmit-only and the query immediately after: every ACK reply `1f 01`, never `4b c1`. Unwind clean. The remaining unmatched differences from Apple: the ~8 MHz clock with 5 us inter-word delay and 10 us CS hold (the Linux S5L controller writes WORD_DELAY 0), the display_sync enable before the reset release, and unknowns (exact SPI source clock, personality values). Next candidates: emulate the word delay (needs a spi-apple change for the 59 KB packet), try ~8 MHz, and re-read the Apple code for any frame between the detect and the firmware.

## Tenth run: Apple order + display_sync pinmux (GPIO55 PERIPH=1), user-approved

Same as the ninth run plus the GPIO55 pinmux (saved 0x00072a82, wrote 0x00072aa2, readback 0x00072aa3, restored exactly on unwind). Detect PASS, five packet+query pairs, every ACK reply `1f 01`, never `4b c1`. Unwind clean (GPIO55 word restored). The display_sync enable is therefore not what the ROM was waiting for. Remaining unmatched: Apple's ~8 MHz clock with the 5 us inter-word delay and 10 us CS hold (WORD_DELAY is written as 0 by the Linux S5L driver), plus the unknown personality values and the SPI source clock.

## Eleventh run (T2 kernel: 0096 word delay, 0097 CS delays): Apple order, mode 0, LSB-first, `--word-delay-us 5`

Detect-only first: DETECT PASS with the delays on (`1f 01` x 8). Then the upload: five transmit-only packet+query pairs, every ACK reply `1f 01`, never `4b c1`. Unwind clean. The 5 us word delay (and the 10 us CS setup/hold from the DT) did not change the outcome. Not verified: that the delay really lengthens the transfer on the wire (the transfer duration was not timed). Still unmatched: ~8 MHz clock, and whatever else is unknown in Apple's sequence (SPI source clock, personality values), plus the possibility that the exported packet itself differs from what the ROM expects.

## Twelfth run (experiment A: transfer timing and reply capture): THE FIRMWARE WAS NEVER SENT

`touch-diag` now timed the firmware transfer: **0.2-0.6 ms for 59,288 bytes** (a 1.984 MHz clock alone needs ~240 ms). The captured reply during the "transfer" is `1f 01` for the first words and zeros after, i.e. only the first few bytes were clocked. The kernel log explains it: `spi_master spi0: transfer completed with 59250 words left to transmit` (and ~59,2xx words left to receive in full-duplex), logged by `apple_spi_transfer_one()` on every attempt, while the ioctl still returned success.
Root cause: in the S5L branch of `drivers/spi/spi-apple.c` (patch 0007's port) the wait loop drops the TXRXTHRESH completion flag after the first threshold event (`xfer_flags &= ~out_status`), so the loop ends once the 16-byte FIFO has been served and the transfer is stopped (`CTRL = 0`) with almost everything unsent. Transfers up to the FIFO size work, which is why every small frame (detect, wake, ATN) behaved. **Every earlier upload run (runs 1-11: rate, chunking, retries, Apple order, display_sync, word delay) transmitted only the first ~16-70 bytes of the packet; none of them tested the firmware upload.** Chunking with 512/1024-byte transfers had the same truncation per chunk. Next step: fix the S5L transfer loop (patch 0098) and rerun the upload.

## Thirteenth run (T3 kernel with patch 0098): the S5L controller hangs on transfers larger than its FIFO

Detect PASS, then the 59,288-byte transfer failed after the 200 ms driver timeout: `spi_master spi0: transfer timed out (remaining 59256 tx, 0 rx), poll=0 status=0x430 out_status=0x0`, `SPI transfer failed: -110`. Status 0x430 = HUNG (bit 4) + RXL_TIMEOUT (bit 5) + TX FIFO level 16 (bits 10:6): the first 32 bytes were queued, the FIFO stayed full and nothing was shifted out, so no threshold event followed. (The "0 rx" in the log is unexplained: this run had an rx buffer. Not yet understood.) Unwind clean; no firmware was acknowledged or confirmed sent.
Reading: until now no transfer larger than the 16-byte FIFO had ever completed on this controller; the old loop's early exit (runs 1-12) hid a hang that only appears when the PIO refill path is needed. Candidate causes: the S5L PIO threshold/refill logic (threshold 1B, IRQ mode), the word delay or CS delay interacting with a transfer that needs refills, or a transfer-count/size limit in the controller (Apple uses PIO below 0x100 bytes and DMA above). Next: a probe that sends valid HBPP ATN frames (`1a a1` + `18 e1` words, the same words the ROM already accepts) of increasing size (32..4096 bytes) with and without the word delay to find where the controller breaks, then fix the driver (or add DMA) accordingly.

## Fourteenth to twentieth runs (T4: patch 0098 rewritten, 2026-10-12): the packet is finally transmitted, and the ROM answers differently

**SPI controller findings (T4, `touch-diag --probe-sizes`, no firmware):** full-duplex transfers still stall above 32 bytes (`polled transfer timed out (remaining len-32 tx, 0 rx), status=0x400433` for 34, 40, 48, 62 and 64 bytes; exactly 32 bytes were pushed every time; 16 bytes fine; 32 bytes takes ~200 ms) so the receive side of the S5L PIO path is still broken. **Transmit-only transfers work**: 64, 256, 1024, 4096 and 8192 bytes complete at wire speed with no kernel error. Apple's own firmware transfer is transmit-only (rx NULL), so the upload path is usable. Measured speed is ~2.3x the requested clock (1.74 us/byte at a requested 1.984 MHz; 0.81 us/byte at 4 MHz; 6.4 us/byte at 500 kHz): the SPI source clock in our device tree is not what the divider assumes. The requested "5 us word delay" lengthens a 59,288-byte transfer by ~2 us/byte (221 ms vs 103 ms), so its unit is not exactly microseconds.

**Upload:** with the transmit-only packet (Apple order, mode 0, LSB-first) the full 59,288 bytes go out (103 ms at 1.984 MHz) and the ACK query now returns **`4c b1`**, not the idle `1f 01` of all earlier runs and not the expected `4b c1`, on all five pairs and **identically for every setting tried**: word delay 0 and 5 us, requested 0.5, 1.984 and 4 MHz. A deterministic ROM status, not a timing artifact. Pattern: the status words Apple's driver knows, `4a d1` (register write OK) and `4b c1` (data OK), and now `4c b1`, all have the form `0x40|n, 0x?1` with the low nibble of byte 0 plus the high nibble of byte 1 equal to 0x17, i.e. a status code n (a, b, c) with a complement check. So `4c b1` is most likely status code 0xc, a ROM response other than "data accepted". Meaning still unknown (checksum or length error? a different accepted state?). Unwinds clean in every run.
Next: find what status code 0xc means in Apple's HBPP/bootloader code (research brief), and re-check the exported packet's framing (its internal checksum/length fields and the 4-byte alignment) against the ROM's rules.

## Twenty-first run set: packet-size ramp (T4, 2026-10-12, user-approved; packets rebuilt from the verified payload by `boot/touch_fw_rebuild.py`, Apple order, mode 0)

Each size sent as one transmit-only data packet (valid Apple format, destination 0), five packet+query pairs, fresh power-up per run. ACK reply after the packet:

| payload (packet size) | reply |
|---|---|
| 64 B (80), 256 B (272), 1008 B (1024), 4096 B (4112) | `1f 01` (idle: the ROM acts as if nothing was received) |
| 16,384 B (16,400) | **`49 69`** (a status word from Apple's accepted set, code 9) |
| 59,272 B (59,288, the full constructed packet) | **`4c b1`** (code 0xc) |

The status depends on the amount sent: nothing recognised up to 4 KiB, code 9 at 16 KiB, code 0xc at the full size. Post-failure diagnostics show the ROM keeps answering the same word to repeated queries, so the state persists until reset. The ROM is clearly receiving data, and its answer is a function of how much; none is `4b c1`. Hypotheses: a status that tracks received length against a size the ROM expects, or a receive-buffer/page boundary effect, or the ROM expecting the data in chunks (the unconstructed pattern is 0x3f0-byte packets with increasing destination offsets). Next: finer ramp (8192, 12288, 24576, 32768, 49152) and a chunked send of the same payload, to map the status code against size and test the chunk pattern.

### Finer ramp (same set-up; user-approved, 2026-10-12)

| packet size | reply |
|---|---|
| 80 ... 4,112 B | `1f 01` |
| 8,208 B, 12,304 B, 16,400 B | `49 69` |
| 24,592 B, 32,784 B, 49,168 B, 59,288 B | `4c b1` |

Two clean thresholds: between 4,112 and 8,208 bytes (reply changes from idle to `4969`) and between 16,400 and 24,592 bytes (to `4cb1`). Packets up to 4 KiB are not recognised at all (idle) even though they are complete and well-formed. This looks like receive-buffer behaviour in the ROM (overflow-style status codes growing with the amount sent), not a content or checksum error. Idea: Apple's DMA path moves the packet in bursts with natural gaps while the ROM drains its buffer; our PIO polled send is one uninterrupted stream. Next: send the same packet as one chip-select interval cut into chunks with a delay after each chunk (`--chunk N --chunk-delay-us D`) and see whether the reply changes; separately, the idle reply to <=4 KiB packets still needs explaining.

### Chunking with pauses, and the 17-18 KiB boundary (2026-10-12, user-approved)

- The full 59,288-byte packet sent as one chip-select interval cut into chunks (58 x 1024 B or 15 x 4096 B) with 0, 200, 1000 or 2000 us pauses after each chunk: `4c b1` every time. Pauses (the ROM draining a buffer) change nothing.
- Boundary between the two non-idle codes: payload 17,408 B -> `49 69`, 18,432 B -> `4c b1` (also 19,456 / 20,480 / 21,504 / 22,528). So: <= 4,112 B idle; 8,208 B to ~17.4 KiB `4969`; >= ~18 KiB `4cb1`. Two thresholds, one around 4.5-8 KiB, one around 17.4-18.4 KiB.
- Note that `4969` (and `4879`) are in the set of words Apple's own detect routine accepts as "ROM alive", while `4cb1` is not: `4969` may be a normal ROM state (data pending?) and `4cb1` an abnormal one. Nothing yet says that any size can produce `4bc1`.
