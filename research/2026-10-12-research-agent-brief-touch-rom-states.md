# Brief for the research agent: what ROM state machine produces idle / `4969` / `4cb1` as a function of the amount sent?

Project: Linux on an iPad Air 2 (J81, A8X/T7001). Repo `<repo>`. Method: memory note "Apple firmware archaeology technique", `tools/ghidra/README.md`. Scratch Ghidra project from the previous touch analyses may still exist (the previous agent reused it); otherwise re-import `__PRELINK_TEXT` (base `0xffffff8002593000`) from `firmware/j81-12B410/ipsw/`. No downloads without asking the user.

## Previous work to read first
`research/2026-10-11-touch-no-ack-analysis.md` (Apple's setup: LSB-first, mode 0, power order, detect frame), `research/2026-10-12-touch-4cb1-analysis.md` (status words, packet format, `0xfc5690` packet builder, bootloader order), `research/2026-10-11-touch-upload-hardware-result.md` (all hardware runs; read the 2026-10-12 sections).

## New hardware facts (all after the SPI transmit path was fixed; the packet is really sent)
After the detect frame passes (`1f 01` x 8), we send ONE valid Apple data packet (`18 e1 30 01`, length in words, destination 0, header sum, payload from the real firmware, payload sum) as a transmit-only SPI transfer, then the query `1a a1`. The reply depends only on the packet size:

| packet size | reply to `1a a1` |
|---|---|
| 80, 272, 1,024, 4,112 bytes | `1f 01` (idle: ROM seems to ignore the packet) |
| 8,208, 12,304, 16,400, 17,424 bytes | `49 69` |
| 18,448 .. 59,288 bytes | `4c b1` |

Unchanged by: SPI clock (0.5-4 MHz requested), word delay, chunking the same chip-select interval into 1-4 KiB pieces with 0-2000 us pauses, repeating the query (the same word every time until reset), Apple's power order, display_sync pinmux. Apple expects `4b c1`. The words `4879` and `4969` are in the set Apple's HBPP detect accepts as "ROM alive"; `4cb1` is not; `4ad1`/`4bc1` are the write/data ACKs.

## Questions (static analysis)
1. **State machine.** Do the status words form a ROM state sequence (`4879` code 8, `4969` code 9, `4ad1` a, `4bc1` b, `4cb1` c)? What does each state mean to Apple's HBPP code: where are they produced/consumed (detect `0xfc1d10`, `0xfc43c4`, `0xfc4560`, ...)? Does the driver or any string name them (ready, busy, overflow, error, crc, timeout)?
2. **Size dependence.** Why would a ROM answer idle for a complete packet up to ~4 KiB, `4969` from ~8 KiB, `4cb1` from ~18 KiB? Look for buffer sizes, DMA/FIFO thresholds, the maximum packet length the ROM or the driver assumes (`0xfff0` is the firmware chunk limit; what is the real bootloader RX buffer size?), and for any statement of how Apple's DMA path (used for >= 0x100 bytes) chunks the transfer: descriptor size, per-descriptor pauses, or ATN/IRQ handshakes between pieces. Is the 59 KB constructed firmware really sent as one SPI transaction by Apple, or does the provider's DMA `transfer` split it?
3. **Small packets ignored.** What must be true for the ROM to react to a small complete data packet (we get idle)? Is a prior command needed (an ATN/ACK pair with the long frame, a "start download" word, a size announcement), or does the ROM only start listening after a specific frame?
4. **Wire form.** Does the ROM expect the bytes in a form different from what we send: SPI frame boundaries (chip select asserted for the whole packet vs per 16-bit word), a 16-bit-word or 32-bit-word transfer mode (`bits_per_word` 16/32 for data packets?), the word delay applied between 16-bit words rather than bytes (Apple's `reg` cells give a 5 us word delay for 8-bit words)? Our transfers are 8-bit words at LSB-first, mode 0. Check `AppleSamsungSPI`/`AppleARMSPIDevice` for the bits-per-word used for data transfers.

## Deliverable
`research/2026-10-12-touch-rom-states.md`: the state table with evidence labels (E/I/U), the explanation (or best-supported hypotheses ranked) for the size thresholds, and a concrete minimal list of changes to try next in `boot/touch-diag.c` (what to send, in what order, with what framing). Evidence = function addresses/offsets and short constants; never raw firmware bytes, decompiler dumps, `.mtprops` contents or device identifiers. Path-limited commit with the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Use `/opt/homebrew/bin/python3`, `command ls`; no hardware access.
