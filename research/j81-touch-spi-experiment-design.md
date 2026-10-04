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

## Implementation status, 2026-10-04: built, statically verified, not run

Payload `.#packages.x86_64-linux.m1n1-hoolock-touch-spi` (base
`m1n1-hoolock-touch-spi-test`; kernel `hoolock-touch-spi-test`, patch `0051`).

- Build: full kernel cross-build exit 0; payload checksums verified.
- Static gate (`boot/test_ssh_stage1.py --touch-diag <base> <payload>`): passes;
  original boot components and the base initramfs are byte-identical, overlay is
  the exact allow-list, the static `touch-diag` ELF has no loader dependency.
- DTB (parsed directly): `/soc/spi@20a08c000/touch-diag@0` with
  `compatible = "rohm,dh2228fv"`, `reg = <0>`, `spi-max-frequency = 0x1e4600`
  (1,984,000 Hz), `spi-cpol`, `spi-cpha`. **No touchscreen compatible anywhere in
  the DTB**, so `apple_z2` cannot bind.
- Kernel image contains the spidev driver. `touch-diag` compiled with
  `-Wall -Wextra -Werror`.
- Host tests: `boot/test_touch_diag_frames.py` (frame bytes match the capture
  analyzer; no register-read/write or execute frames in the source; defaults match
  this design). The offline suite is at 20 passed, 7 skipped.

Next, in order, each needing the user at the device:
1. boot; confirm `/dev/spidev0.0` exists and run `touch-diag spi-check`
   (configures the node, reads mode/bits/speed back, sends nothing, powers nothing);
2. run A, B, C from the run matrix, each with an explicit go-ahead.

## Hardware result 1, 2026-10-04: spidev node and `spi-check` (no traffic)

Booted `m1n1-hoolock-touch-spi` (cold boot, recorded session, private). Nothing was
powered and no frame was sent.

- `/dev/spidev0.0` exists (char `153,0`); `spi0.0` (`modalias spi:dh2228fv`) is bound
  to the `spidev` driver. `apple-z2` is registered but **not** bound to the child, as
  designed. No touchscreen input device; `input0` is `gpio-keys`.
- `touch-diag spi-check` read the settings back correctly for the design's default
  (mode 3, 8 bits, 1,984,000 Hz), mode 0, and 500 kHz; all exit 0.
- `touch-diag status` afterwards is identical to the pre-experiment baseline: LDO14
  off (`0x00`, voltage `0x14`), clock `0x800002ee`, GPIO words unchanged.
- The kernel log contains no spi, spidev or touch messages.

Ready for run A (mode 3, 1.984 MHz), which needs the user's explicit go-ahead and is
run by the user over SSH.

## Hardware result 2, 2026-10-04: run A (mode 3, 1.984 MHz) gets a response

Run by the user over SSH after giving the go-ahead:
`touch-diag run --execute --approve-pmu-write --spi-dev /dev/spidev0.0 --spi-mode 3 --spi-hz 1984000`.
Power-up and unwind were identical to the earlier diagnostic (clock register now
`0x000802dc`, LDO14 `0x04`, restored to `0x00`, clock back to gate-off with divider
732). Boot IRQ: falling edge again, line low afterwards.

| Frame | TX | RX |
| --- | --- | --- |
| dummy (before reset release) | `1a a1` + 7 x `18 e1` | `00` x 16 |
| wake | `ee` at byte 0 and 14, others `00` | `f8 80` x 8 |
| ATN/ACK short | `1a a1` | `f8 80` |
| ATN/ACK long | `1a a1 18 e1 18 e1 18 e1` | `f8 80` x 4 |

Reading (E for the bytes, I for the interpretation):

- **The bus is alive.** Before reset release the line returns all `00` (controller
  held in reset); after release every frame returns the same non-trivial two-byte
  word `f8 80` repeated, not all-`00`/`ff`. A floating or stuck MISO would not give
  this pattern, so the clock, MOSI/MISO pads, chip select and mode are at least
  electrically working.
- **It is not the recovered ACK.** `f8 80` is neither `4b c1` (data ACK) nor `4a d1`
  (register-write ACK). The same word answers the wake, the short ATN and the long
  ATN, regardless of what was sent, which looks like an **idle/not-ready status the
  ROM clocks out continuously** (a constant output register) rather than command
  responses. That reading is **I**.
- **Mode/rate are not confirmed.** Mode 3 at 1.984 MHz produced a stable pattern, but
  a shifted or misaligned sample of a different word is possible; the design's
  stop condition for run A (anything other than `00`/`ff`) is met, so runs B and C
  are not required, but a **mode 0 contrast run** would show whether the word
  changes with the mode, which separates a true status word from a sampling artifact.
- Nothing was written to the controller beyond the three handshake frames; no
  firmware, no register write, no calibration.

## What this changes

The question "does the controller answer SPI at all" is answered yes. The unknown
moves to: what `0xf880` means (idle status of the ROM, or bit-shifted data), and
which first frame the boot ROM expects (Apple's driver starts with firmware chunks,
not queries). Next evidence should add exactly one variable per run: mode 0 at the
same rate (contrast), or a repeat of run A to confirm the word is stable across
power cycles. No firmware upload is justified by this result alone.

## Hardware result 3, 2026-10-04: run B (mode 0, 1.984 MHz), identical response

Run by the user over SSH with the go-ahead:
`... --spi-dev /dev/spidev0.0 --spi-mode 0 --spi-hz 1984000`. Same power-up, same
boot IRQ edge (falling), same unwind; the clock register ended at `0x800002dc`
(it started there because run A had already left the divider at 732).

RX: dummy all `00`; wake `f8 80` x 8; short ATN `f8 80`; long ATN `f8 80` x 4.
Byte-for-byte the same as run A.

**What this does and does not show.** Modes 0 (CPOL 0, CPHA 0) and 3 (CPOL 1,
CPHA 1) both sample data on the **rising** clock edge; they differ only in the idle
level of the clock and the first-edge phase. An identical result therefore says the
word is stable under that change and is not a clock-idle artifact, but it does **not**
test the sampling edge. The decisive contrast is mode 1 or mode 2 (sample on the
falling edge): if `f8 80` is a real word clocked correctly, it should change (a
different, likely shifted, pattern); if the line carries a constant level pattern
unrelated to the clock phase it would stay the same.

Also still true: the same word answers all three different frames and does not depend
on the TX bytes, and it is not a recovered ACK (`4b c1`, `4a d1`). Two independent
runs (A and B, two separate power-ups) show it is stable across power cycles.

## Updated next step

One more contrast run, mode 1 at the same rate (falling-edge sampling), then
optionally 500 kHz. Each needs the user's go-ahead. Nothing here justifies sending
firmware or any register write.

## Hardware result 4, 2026-10-04: run C (mode 1, 1.984 MHz), identical response

Run by the user over SSH with the go-ahead
(`--spi-mode 1 --spi-hz 1984000`). Same power-up/unwind, same boot IRQ edge.
RX byte-for-byte as in runs A and B: dummy all `00`; wake `f8 80` x 8; short ATN
`f8 80`; long ATN `f8 80` x 4.

Mode 1 samples on the **falling** edge, so together with A (mode 3) and B (mode 0),
both sampling edges now give the same word. The reply therefore does **not** depend
on the sampling edge or the clock idle level in any way these runs can resolve, nor
on the TX bytes, nor on the power cycle.

## Correction to the design's mode inference

The design inferred mode 3 from Apple's controller resetting its channel
configuration to `0xd`, which was read with the **Samsung S3C** `CH_CFG` bit layout
(CPHA = bit 2, CPOL = bit 3). That was the wrong register layout. The kernel's
`spi-apple` S5L port (the driver actually driving this controller) uses
`CFG` bit 0 AUTO_TX, **bit 1 CPHA, bit 2 CPOL**, bit 3 ROLESEL. In that layout
`0xd = AUTO_TX | CPOL | ROLESEL`: **CPOL = 1, CPHA = 0, i.e. SPI mode 2**, as master.
Apple writes `0xd` as the per-transfer base value, and no per-command code in the
decompiled controller changes the CPHA/CPOL bits, so the stock mode for Apple's
transfers is most likely mode 2, with the clock idling high (which still agrees
with "ensuring S_CLK is high"). Modes 0, 1 and 3 do not match that, so **mode 2 has
not been tested**. This weakens, but does not by itself explain, the constant
`f8 80`: three modes gave one word, which may mean the word is not shifted data at
all (for example a status pattern or a signal not coupled to the data phase).

## Updated next step

1. Mode 2 at 1.984 MHz (Apple's decoded default); the same four frames.
2. If still `f8 80`: a much lower rate (Apple's Z1 EVT used a 10 us period, about
   100 kHz) to rule out an excessive clock; then stop and re-read the controller's
   CS and clock configuration before more power cycles.
Each run needs the user's go-ahead. Still no firmware, no register write.

## Hardware result 5, 2026-10-04: run D (mode 2, 1.984 MHz) shifts the word by one bit

Run by the user over SSH with the go-ahead (`--spi-mode 2 --spi-hz 1984000`). Same
power-up/unwind. Boot IRQ: this time the first event read was a **rising** edge
(level before 1, after 0), unlike runs A-C, which saw a falling edge first. The
line ends low as before; the event order is noted but its cause is unexplained (**U**).

RX: dummy all `00`; wake `f0 01 f1 01 f1 01 ...`; short ATN `f0 01`; long ATN
`f0 01 f1 01 f1 01 f1 01`.

**The word is clocked data, not a level.** Modes 0, 1, 3 gave the bit stream of
`f8 80` repeated (`1111 1000 1000 0000` per 16 bits). Drop the first bit of that stream
and re-group into bytes: `f1 01 f1 01 ...` (`1111 0001 0000 0001`). Mode 2 shows
exactly that, with the first word `f0 01` (a different leading bit) as the one-bit
alignment edge effect. So the controller really is sampling a **periodic 16-bit bit
pattern** from the slave, and the sampling phase of the first bit moves the
alignment by one bit. This shows the clock, MISO path and chip select work, and that
the pattern repeats with a 16-bit period.

**It still does not answer our frames.** The same periodic pattern comes back for the
wake, short and long ATN frames, and is unchanged by the bytes sent. It matches
neither recovered ACK (`4b c1`, `4a d1`) at any of the 16 rotations of the pattern
(rotations of `f880` include `f101`, `e203`, `c407`, `880f`, `101f`, `203e`, `407c`,
`80f8`, `01f1`, `03e2`, `07c4`, `0f88`, `1f10`, `3e20`, `7c40`). The best reading is a
constant **idle/not-ready output of the boot ROM**, with the true word boundary
ambiguous by rotation (**I**).

## Interpretation and what is left

- Bus bring-up is **done**: power order, reset polarity, clock, mode (any), rate and
  chip select all produce a live, clock-dependent response.
- The remaining open question is the ROM's expected first packet. Apple's bootloader
  starts with the firmware download chunk and only then issues the short ATN/ACK to read
  `4b c1`; the queries sent here are not part of that flow before firmware, so a
  constant idle word is the expected answer to them.
- Two non-firmware variables remain untried: the `function-enable_download` call Apple
  makes around reset ("fw download mode"; absent from the J81 ADT text dump) and the
  `display_sync` GPIO55 drive. Either could be what puts the ROM into download mode.
- **Going further means sending firmware**, which is the project's standing gate: the
  recovered packet is the exact constructed firmware Apple's own driver sends to this
  controller in one `18 e1` packet, followed by an ATN/ACK that must read `4b c1`.
  That needs the private asset (from the iPad5,3 IPSW), a dedicated approved test, and
  the user's explicit decision. It is not started.
