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
