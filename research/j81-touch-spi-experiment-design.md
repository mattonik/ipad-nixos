# J81 touch SPI experiment: design (not built, not run)

Date: 2026-10-04. Builds on the
[power-up diagnostic](j81-touch-diagnostic.md) (controller wakes, boot IRQ seen),
the [recovered framing](j81-z2-n1-transport-framing.md), the
[GPIO polarity](j81-touch-gpio-polarity-a8x.md) and
[clock](j81-touch-clock-kclt-a8x.md) decodes. Static analysis for the new
inputs; labels **E** evidence, **I** inference, **U** unknown.

## Question

After the proven power-up, does the controller answer a **minimal, read-only**
SPI exchange in the framing recovered from Apple's driver, and with which SPI
mode and rate? Nothing else: no register write, no firmware, no calibration.

## New facts for this design

- **E: the controller is in boot-ROM state after reset.** Apple's driver does not
  probe for running firmware over SPI; its "has firmware" test is a stored flag,
  and the bootload path runs up to three firmware download attempts. So the
  register read of the chip version (`0x10008ffc`, expect `0x434d11a0` for N1) that
  Apple issues belongs to the **post-firmware** calibration step and may not be
  answered by ROM. It must not be the first or only success criterion.
- **I: SPI mode 3 (CPOL = 1, CPHA = 1).** Apple's Samsung SPI controller resets
  its channel-config word to `0xd` (RX on, CPHA, CPOL, in the Samsung layout), and
  Apple explicitly ensures "S_CLK is high" before releasing reset, i.e. the clock
  idles high. Mode 3 is the first candidate; mode 0 the fallback.
- **I: rate about 2 MHz.** In the ADT, child `reg` words are
  `[cs, rate-field, flags, extra]`: `flags` byte 3 is bits-per-word (`0x08` = 8,
  checked by the controller's validity test) and the rate field behaves as a
  frequency in 16 kHz units: the J81 Mesa node has an explicit `spi-frequency` of
  8,000,000 and `reg[1] = 500` (500 x 16 kHz = 8 MHz exactly), while touch has
  `reg[1] = 124`, giving **1.984 MHz**. The `0x1388` (5000) extra word is
  unexplained (a delay or chip-select timing in ns is plausible; **U**). The
  earlier 5000 hit in the SPI-NOR flash code is a different class.
- **E: words are 8 bits wide**; the frames in the framing note are byte streams.
- **U: whether `function-enable_cs` (GPIO51, 5 us delay) must be driven.** GPIO51
  is also the SPI3 CS pad. The first runs rely on the controller's own chip select.

## Approach

A separate RAM-only payload `m1n1-hoolock-touch-spi`, never merged into the
default payloads:

1. **Kernel config:** `CONFIG_SPI_SPIDEV=y` (currently off), nothing else.
2. **DT (that payload only):** a child of the SPI3 master with
   `compatible = "rohm,dh2228fv"` (a spidev test binding), `reg = <0>`,
   `spi-cpol; spi-cpha;` and `spi-max-frequency = <1984000>`. **Not** the
   `apple,j81-touchscreen` compatible: patch `0011` makes `apple_z2` match that, and
   binding it would start reset, boot and firmware upload on its own.
3. **Userspace:** extend `touch-diag` with an optional `--spi /dev/spidev0.0`
   stage, driven with the spidev ioctls (mode, speed, bits per word, full-duplex
   transfer). RX bytes go to the private session log only.

## Sequence

Power-up exactly as in the diagnostic (clock, LDO14, GPIO95, reset released, wait
for the GPIO84 falling edge), then, with a timeout on every step and the same
unwind (reset asserted, GPIO95 low, LDO14 restored, clock disabled) at the end:

| # | Frame | Why | Reading |
| --- | --- | --- | --- |
| 1 | the 16-byte dummy transfer (`1a a1` + 7 x `18 e1`) before reset release | Apple does it to leave the clock high | RX discarded, but must not hang the bus |
| 2 | wake command (16 bytes, `ee` at 0 and 14) | Apple sends it before commands after >100 ms idle | RX logged |
| 3 | short ATN/ACK `1a a1` | the HBPP handshake used after every chunk | status word; `4b c1` would match the data-ACK value |
| 4 | long ATN/ACK `1a a1 18 e1 18 e1 18 e1` | the form used to read register replies | RX logged |

Frames 1 to 4 change no controller state that Apple's own bootloader does not
change before firmware. No `e118` data chunk, no `1e 33` write, no `1d 53` execute.
Register read `1c 73` is **excluded** from run 1 (ROM state, see above); a later
run may add it only after firmware, which is out of scope here.

## Run matrix

| Run | Mode | Rate | Stop condition |
| --- | --- | --- | --- |
| A | 3 | 1.984 MHz | RX contains anything other than all-`00`/all-`ff` echoes |
| B | 0 | 1.984 MHz | same |
| C | the better of A/B | 500 kHz | same |

Each run is a fresh cold boot (the controller must be reset), user go-ahead each
time (D2207 and PMGR writes again), and ends with the standard unwind and a
read-only `status`.

## Reading results

- A status word that matches a recovered constant (`4bc1`, `4ad1`) or any stable
  non-trivial, repeatable response across the four frames: protocol and mode/rate
  are plausible. Record the exact bytes in the private log and the *class* of
  response in the notes.
- All `00` or all `ff` in every mode and rate: the failure is the bus (mode, rate,
  chip select, `enable_cs`) or ROM state, not the framing. That is **inconclusive**
  about the protocol; the next step would be the chip-select/`enable_cs` question.
- Hangs or a stuck IRQ line: abort and unwind; do not retry blindly.

## Explicit non-goals and gates

No firmware, no calibration, no register write, no `apple_z2` binding, no touch
child with a Z2 compatible, no persistent change. Because this is the first SPI
traffic to this controller, each run needs the user's explicit approval at run
time and is recorded to the repository before the next run.

## Build checklist (for the implementation step)

1. Patch: `CONFIG_SPI_SPIDEV=y` in a new defconfig; DT child in the touch-spi
   payload's DTB only. Verify `spidev` binds and `/dev/spidev0.0` appears with the
   controller **still unpowered** (no transfer yet).
2. Extend `touch-diag` with `--spi`, keeping `plan` and `status` read-only, adding
   a `--dry-run` that opens spidev and prints the planned frames without sending.
3. Static gate extension and host tests for the frame builders (already modeled in
   the capture analyzer).
