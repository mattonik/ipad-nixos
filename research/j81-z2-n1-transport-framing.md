# J81 touch transport framing from Apple's iPad5,3 driver

Date: 2026-10-04. Static analysis only: Ghidra decompilation of
`AppleMultitouchSPI` (MultitouchSoftware-275.27, load `0xffffff8002fb7000`) in
the iPad5,3 iOS 8.1 (12B410) kernelcache, SHA-256 `19c277d6...cc28bf`. No
device access, no SPI transaction, no private asset content. Only protocol
constants from Apple's code are recorded. Evidence labels: **E** read in the
decompilation, **I** inference, **U** unknown.

This closes the "recover the `0xe118` fields and the ACK predicate from
disassembly" item in [the touch bring-up audit](j81-touchscreen-bringup-offline.md)
and replaces its reliance on the 2008 openiBoot profile with the actual Apple
iOS 8.1 driver for J81's `AppleMultitouchN1SPI` class.

## Transport primitive

- **E:** every exchange is one full-duplex SPI transfer through a provider
  virtual `transfer(tx, txLen, rx, rxLen, 0)`. Bootloader transfers log both
  buffers with the same helper. Larger data packets (>= 0x100 bytes) may use a
  DMA variant when the driver's DMA flag is set; the PIO form is the same bytes.
- **E:** all command frames use a **16-bit byte sum** checksum, stored **high
  byte first**, over the bytes after the two-byte opcode.
- **E:** 32-bit addresses and values are emitted as 16-bit-word-swapped
  bytes: for value `v` the bytes are `v[15:8], v[7:0], v[31:24], v[23:16]`.

## Command frames (all E)

| Frame | TX bytes | Checksum covers | Notes |
| --- | --- | --- | --- |
| ATN/ACK (short) | `1a a1` (2) | none | RX 2 bytes, read as a big-endian status |
| ATN/ACK (long) | `1a a1 18 e1 18 e1 18 e1` (8) | none | status bytes taken from the RX |
| Read register | `1c 73` + addr(4) + sum(2) = 8 | addr bytes | the value is read back by a following long ATN/ACK |
| Write register | `1e 33` + addr(4) + mask(4) + value(4) + sum(2) = 16 | the 12 body bytes | success predicate below |
| Execute | `1d 53` + addr(4) + `00 01 00 00` + sum(2) = 12 | the 8 body bytes | "about to execute"; start firmware at the personality's execute address |
| Calibration request | `1f 01` (2) | none | RX 2 bytes; the driver then sleeps ~65 ms and polls a short ATN/ACK |
| Wake | 16 bytes: byte 0 = `ee`, byte 14 = `ee`, all others `00` | none | only sent if more than 100 ms elapsed since the previous wake; 2 ms delay after |
| Data/firmware chunk | `18 e1` + header(12) + payload + sum(4) | per the legacy layout | payload at most `0x3f0` bytes, padded to a multiple of 4; transfer length = payload + 16 |

The data chunk's 16-byte overhead and `0x3f0` (1008-byte) maximum are
identical to the legacy builder's 4-1008-byte domain already modeled in
[`boot/analyze_touch_capture.py`](../boot/analyze_touch_capture.py).

## ACK status words (E)

- After a data chunk the driver issues a short ATN/ACK and requires status
  **`0x4bc1`** (bytes `4b c1`), retrying the whole chunk up to five times.
- After a register write the driver issues a short ATN/ACK and requires
  **`0x4ad1`** (bytes `4a d1`). Anything else logs "Error writing" and fails.
- The calibration-end ACK return value is not compared; only the transfer
  success is checked.

The two status words differ, so a single "ACK matches 4bc1" predicate (the
legacy analyzer's original) is not enough. The analyzer now reports both.

## Bootload order (E)

`MTSPIBootloader_Z2::bootloadDevice()` (inherited unchanged by N1) runs, and
stops at the first failure: firmware download -> proximity calibration
download -> calibration download -> `performCalibSeq` -> execute. The firmware
step selects the **Constructed Firmware** property when the driver's
"constructed" flag is set (the J81 case), otherwise the unconstructed
`Firmware` property chunked as above; the loaded blob must be at most
`0x10000` bytes (the recovered J81 asset, 59,288 bytes, fits).

`MTSPIBootloader_N1::performCalibSeq()`:

1. read chip version at `0x10008ffc` (N1 value `0x434d11a0`; Z2 value `0x5a020028`);
2. write the personality's reference-clock-divider address/value
   (`ref_clk_div_addr/val`), mask `0xffffffff`;
3. write `0x10003058 = 6`;
4. write personality `const_cal_addr` with value 2 (N1 chip version) or
   `const_cal_val` otherwise;
5. if the personality defines `clk32-clock-enable-addr`, write it with
   `clk32-clock-enable-val`;
6. read `0x10003800` and log "SPI_APU_EN";
7. send the calibration request, wait, poll ATN/ACK.

The four personality keys are read from the owner's property table
(`const_cal_addr/val`, `ref_clk_div_addr/val`, `clk32-clock-enable-addr/val`);
their J81 values are **U** here and not duplicated in this note.

## Reset and wake context (E)

- Reset asserts, then power-down/up through `function-clock_enable`,
  `function-power_ana`/`power_ldo`, an `function-enable_download` call that
  turns firmware-download mode on before reset release and off afterwards
  ("enabling/disabling fw download mode"), then the personality's reset
  deassert delay. **New:** `function-enable_download` is a property the J81
  ADT multi-touch node does not list in the captured text dump; it may be
  resolved from the personality or be optional (**U**).
- A "Z1 EVT" workaround forces `spiClockPeriod` to 10000 ns for one hardware
  ID only; it does not apply to the J82/N1 personality.

## What this changes

- **Linux `apple_z2` is closer to Apple's driver than assumed.** The upstream
  register-read/write and HBPP framing (see the audit) use the same 8/16-byte
  commands; the `1a a1` and `e118` constructs match. The remaining deltas are
  the constructed-firmware single packet, the two distinct ACK words and the
  N1 calibration sequence above.
- The offline analyzer now recognizes read/write/execute/wake/calibration
  frames, verifies their checksums, and separately reports the `4bc1` and
  `4ad1` ACK status. Addresses and values remain unreported.
- Still **U**: the J81 SPI mode and clock, the exact KLCT index, GPIO polarity
  of reset/power, `function-enable_download`, and the personality values above.
  A captured native-boot exchange remains the only evidence for any of them.

## Not done / not safe

Nothing here authorizes a touch child, a transfer, or sending any frame. These
are the byte layouts Apple's code builds; a mismatch on this exact hardware
would still be undefined behavior for the controller, and the ADT, reset
polarity and power-up order remain unresolved.
