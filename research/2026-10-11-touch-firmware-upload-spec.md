# J81 firmware upload: offline specification and decision gate

Static review only, 2026-10-11.  No hardware, build, private calibration, or
firmware bytes were committed.  **E** means recovered from the iPad5,3 iOS 8.1
driver or the authorized private asset inventory; **I** is an inference; **U**
remains unknown.

## The one thing Apple sends first

| Order | Action | Evidence and required result |
| --- | --- | --- |
| 0 | Establish the existing approved power/reset state; optional download-mode callback is non-gating. | **E:** `touch-diag`'s clock, LDO14, GPIO95, reset sequence reaches the ROM boot IRQ. The ROM does not answer the pre-upload queries. |
| 1 | Send the `Constructed Firmware` plist data in one SPI transfer. | **E:** `MTSPIBootloader_Z2::bootloadDevice()` selects `Constructed Firmware` for J81's constructed flag. The 12B410 value is 59,288 bytes, starts `18 e1`, is four-byte aligned, and is below the driver's `0x10000` limit. It is already Apple's completed packet; do not add a header, split it into `0x3f0` chunks, pad it, or recompute a checksum. |
| 2 | Send short ATN/ACK query `1a a1`. | **E:** the N1 driver requires big-endian reply `4b c1` after a data packet and retries the *same packet plus query* at most five times. Any other reply is failure. |
| 3 | Download proximity calibration and calibration, then perform N1 calibration. | **E:** this follows firmware in `bootloadDevice()`. Their private byte envelopes are not reconstructed; this specification does not export or authorize them. |
| 4 | Execute firmware. | **E:** Apple emits `1d 53` + word-swapped execute address + `00 01 00 00` + big-endian 16-bit byte sum. J81's personality execute address is `0x10003400`. This is after calibration, not a substitute for it. |

The requested “pre-upload version read” is a sequencing error: **E** the N1
read of `0x10008ffc` occurs in `performCalibSeq()` *after* firmware and the two
calibration downloads.  It must not be used as a boot-ROM probe.

The generic, unconstructed data path does use `18 e1`, a 12-byte internal
header, a four-byte trailing sum, and at most `0x3f0` bytes per payload.  That
is **not** the J81 path: interpreting the already-constructed 59,288-byte
packet through it would change the bytes Apple sends.

## Offline asset/exporter

`J81.mtprops` contains exactly personality `C1F15,2`, with packet type `Z2`,
version `0x0381.bin`, reset interval `432000`, and `Constructed Firmware`.
The existing bounded inspector validates the 59,288-byte payload and expected
SHA-256 before export.  `boot/touch_fw_packets.py` then emits, to a private
directory, only:

1. the verified constructed firmware transfer verbatim; and
2. the public two-byte `1a a1` ACK query.

It prints lengths and SHA-256 values only; files are exclusively created with
mode 0600 and a repository destination must be Git-ignored.  The host test
uses a synthetic packet only.  It verifies verbatim preservation and the
`1a a1` framing; the known expected reply is `4b c1`.

```sh
/opt/homebrew/bin/python3 boot/test_touch_fw_packets.py
/opt/homebrew/bin/python3 boot/touch_fw_packets.py \
  firmware/j81-12B410/touch/J81.mtprops firmware/j81-12B410/touch/upload-packets
```

The second command is an offline file export, not an upload.  It will reject
any asset that is not the recorded identity unless an explicit expected hash is
provided.

## Linux comparison and implementation route

Mainline `apple_z2` is useful for the normal report protocol and for the
unconstructed Z2FW container path.  It is not a J81 uploader: its version-1
container is different, its blob transfer does not inspect the ACK RX bytes,
and its nonfatal 20-ms completion wait cannot replace N1's `4b c1` predicate.
Do not wrap J81 data in Z2FW or bind the J81 compatible to test this.

The existing SPI3 spidev test child and `touch-diag` transport are the right
first implementation vehicle.  A userspace sender can make a full-duplex,
one-chip-select 59,288-byte transfer and capture the two reply bytes before
any new kernel driver exists.  That is a future, separately approved hardware
operation; the exporter deliberately has no SPI code.

## Safety assessment

**E:** the upstream Z2 driver describes firmware upload as volatile; a reset
returns the controller to ROM.  **I:** Apple's J81 bootloader uses the same
RAM-addressed boot protocol, so its constructed packet is likely volatile as
well.  There is no evidence in the recovered J81 sequence of erase/program
commands or a nonvolatile address space.  This is not proof that a malformed
packet cannot reach undocumented persistent functionality.

Worst established case: a bad or interrupted transfer leaves this boot attempt
in ROM/bootloader, with an asserted or stalled IRQ and no touch until reset;
the recoverable action is assert reset, disable GPIO95, restore LDO14/clock,
then cold reboot.  Stop immediately on unexpected sustained current/heat,
SPI timeout, an IRQ stuck in an unexpected state, a reply other than `4b c1`,
or a failed unwind.  Do not retry automatically.  Respect the already proven
6.0-V LDO14 setting, 15-ms reset-deassert delay, and mode 2/1.984-MHz starting
point.  Exact maximum SPI transfer size, chip-select continuity, and
nonvolatile-write absence are **U**.

## Proposed user-approved experiment

1. Boot the isolated `m1n1-hoolock-touch-spi` payload; confirm the spidev test
   child is bound, no `apple_z2` child is bound, and baseline power-off state.
2. Run existing power/reset diagnostic with mode 2 and 1.984 MHz.  Require the
   normal boot IRQ and a clean read-only status before proceeding.
3. Copy the exporter output to the device privately.  Before transmission,
   re-check only packet length/hash and configure spidev without transmitting.
4. In one explicit run, transmit `00-firmware-transfer.bin` as one full-duplex
   SPI message with CS held for the message.  Send `01-data-ack-query.bin` only
   after the transfer completes.  Record RX privately.
5. Continue only for `4b c1`; otherwise abort and perform the recovery above.
   A matching ACK proves receipt of this packet, not working touch, calibration,
   execution, or a safe kernel driver.
6. If and only if the user separately approves the next phase, reconstruct the
   two calibration transfers and the execute transition from Apple evidence;
   then assess the post-execute interrupt/report protocol before writing a
   driver.

## Superseded interpretations

- The older `0x3f0` chunk builder is an unconstructed/calibration reference,
  not a J81 constructed-firmware encoder.
- A pre-firmware `1a a1` response or chip-version read is not a valid success
  gate; `4b c1` belongs immediately after the constructed transfer.
- Linux `apple_z2` is not safe to try first merely because it has a firmware
  uploader: its container and completion semantics differ.
