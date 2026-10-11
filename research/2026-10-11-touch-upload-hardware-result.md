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
