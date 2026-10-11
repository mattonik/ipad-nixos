# Why the J81 touch ROM ignored the firmware packet: static analysis (2026-10-11)

Static analysis only. No hardware, no download, no firmware or `.mtprops` bytes, no device identifiers.
Source: Ghidra (full flat import of `__PRELINK_TEXT`, base `0xffffff8002593000`, auto-analysis) of the iPad5,3 12B410 kernelcache, `AppleMultitouchSPI` (MultitouchSoftware-275.27, load `0xffffff8002fb7000`), `AppleSamsungSPI` (`0xffffff8002900000`), the `AppleARMSPIDevice` code in `AppleARMPlatform` (`0xffffff8002671000`), the J82 personality in the kernelcache's prelink plist, and the captured J81 ADT text. Labels: **E** read in code or data, **I** inference, **U** unknown.

## Result in one paragraph

The ROM was not silent or "idle": it has been answering with a valid Apple HBPP status word all along, and our controller was shifting **LSB-first vs MSB-first the wrong way round**. The J81 `multi-touch` node's SPI `reg` cells make Apple's SPI controller driver configure the touch device **LSB-first** (and mode 0, 8-bit words, about 8 MHz, 5 us word delay, 10 us chip-select delay). `touch-diag` (spidev default) shifts MSB-first, so (a) every byte we send reaches the ROM bit-reversed and is not a valid HBPP command, and (b) every reply byte reaches us bit-reversed. The "constant idle pattern" `f0 01 f1 01 ...` / `f8 80 ...` is exactly the ROM's idle word `0x1f01` read bit-reversed, and `0x1f01` is one of the seven words Apple's HBPP-detect code accepts. `function-enable_download` is **not** the cause and there is nothing to drive for it on J81 (E, below).

## 1. The decisive finding: SPI parameters come from the child's `reg` (answers Q3 and, indirectly, Q5)

`AppleARMSPIDevice::start` (`0xffffff80026720c8`) requires the `reg` property to be at least 0x20 bytes and stores 32 bytes (`0xffffff8002671ce0`). `AppleSamsungSPIController` turns those eight little-endian words into controller settings in `0xffffff8002900e10` (config), validated by `0xffffff8002900cf8`, used by the transfer routine `0xffffff8002900f64`. The J81 node's cells and what the code does with them (E for the formulas; the register meanings are I, taken from the Linux `spi-apple` register layout that the project's patch 0007 already uses and which the decompiled constants match):

| reg cell / byte | J81 value | Use in Apple's code | Meaning |
| --- | --- | --- | --- |
| word 0 | 0 | chip-select index (`function-spi_cs0` lookup) | CS0. The SPI3 node's `function-spi_cs0` is the ADT `null` function (E), so Apple does not toggle a GPIO for CS here. |
| word 1 | 124 | divider = ceil(value x nclk_Hz / 1e9), reg `0x30` | SCK **period in ns** (about 8.06 MHz upper bound). Cross-check: the audio codec on SPI1 has 83 (12 MHz) and another SPI1 child 500 (2 MHz); both are plausible. The repo's "124 x 16 kHz = 1.984 MHz" was a mis-reading. The exact rate depends on the nclk rate (U). |
| byte 8 | 0 | non-zero sets CFG bit 2 | CPOL = 0 |
| byte 9, bit 0 | 0 | sets CFG bit 1 | CPHA = 0, so **SPI mode 0** |
| byte 9, bit 1 | 0 | would set CFG bit 20 (version 1) | not used |
| byte 10 | **1** | if byte 10 == 0 the code ORs in controller field `+0x120`, which for `spi-version 1` (the J81 SPI3 value) is `0x2000` = bit 13 | bit 13 is `MSB_FIRST` on the S5L controller (patch 0007). Byte 10 = 1 leaves it clear, so the device is shifted **LSB-first**. |
| byte 11 | 8 | word size 8/16/32 only | 8-bit words |
| word 3 | 5000 | reg `0x38` = ceil(5000 ns x pclk_Hz / 1e9) | **inter-word delay 5 us** (`WORD_DELAY`) |
| word 4 | 10000 | `(10000 + 999) / 1000` = 10; delay (`0x23a3be0`, microseconds) executed after CS assert before the first clock and again after the last clock before CS release | **CS setup and hold, 10 us** |

The values 5000 and 10000 that `j81-touchscreen-bringup-offline.md` called "private values not established as dimensions" are these two delays (E: same cells). The `0xd` that `j81-touch-diagnostic.md` and `touch-diag.c` decode as "CFG = AUTO_TX | CPOL | ROLESEL, hence mode 2" is the value written to controller register **0** (`+0x154`, written with `(*0x5e0)(this, 0, ...)` at the start of every transfer), which in the Linux layout is CTRL = RUN | TX_RESET | RX_RESET, not the configuration register (E for the write target, I for the layout). The per-device CFG is built in `0xffffff8002900e10` and has CPOL/CPHA from the cells above. **Mode 2 was never Apple's mode.**

No other SPI parameter source exists (E): the J82 personality in the kernelcache has only `clk32-clock-enable-addr/val`, `fw-execute-addr`, `cal-dl-addr`, `fll-mval(-addr)`, `prox-cal-addr`, `mt-merge-personality`, `reset-deassert-delay` (15), `touch-size-id`, `parser-type/options`, `AutomaticallySetOperatingMode`, `HIDServiceSupport`, `IONameMatch`. The only runtime override is the Z1-EVT clock-period hack (`0xffffff8002fbcf30`), which applies to `multi-touch,z1` hardware only. There is no separate bootloader-phase configuration: the same device config is used for the HBPP detect, the firmware packet and the later report protocol (E: nothing reconfigures the device between them).

### Why this explains the hardware results (E arithmetic, I conclusion)

The accepted HBPP reply words in Apple's detect routine (below) are `18e1 1aa1 1f01 4879 4969 4ad1 4bc1`. Bit-reversing each byte of a repeating `1f 01` gives `f8 80 f8 80 ...`, the pattern the project recorded as "mode 2 idle `f880`". A one-bit sampling shift of that stream gives `f1 01 f1 01 ...` (with a start-up first word `f0 01`), which is every other recorded reply. A short script confirms that, of all rotations, bit-reversals and inversions of the observed 16-bit pattern, the only match with the accepted set is `0x1f01` after bit reversal. So the ROM has been presenting HBPP idle (`0x1f01`) to every frame; our frames, sent MSB-first, were bit-reversed garbage to it (`1a a1` arrives as `58 85`, the firmware header `18 e1` as `18 87`), so it never recognised a command, a data packet or an ACK query. That also explains why nothing changed with 4x slower clocks, chunking, repeats and delays.

## 2. `function-enable_download` (answers Q2)

- **E:** `0xffffff8002fc13b4` (`downloadModeSetEnabled`, vtable slot `+0x858`) looks up `function-enable_download` on the provider only (`getProperty` through `0xffffff80026616a8` / `0xffffff8002661700`, which requires an OSData of at least 8 bytes: phandle + 4-char target + args; no parent search). If the property is missing it returns `kIOReturnUnsupported` (`0xe00002c7`).
- **E:** the captured J81 `multi-touch` node (compatible `multi-touch,j82`) has `function-clock_enable`, `function-power_ana`, `function-power_ldo`, `function-reset`, `function-display_sync`, `function-enable_cs` and **no** `function-enable_download`; the J82 personality has no equivalent key either. No other node in the ADT carries it.
- **E:** all four call sites ignore the return value: reset assert/release (`0xffffff8002fc0b58`), the HBPP detect (`0xffffff8002fc1d10`), `finishStarting` (`0xffffff8002fc074c`) and `bootloadDevice` (`0xffffff8002fc3fb4`). On J81 each one is a logged no-op returning "unsupported".
- **Resolution:** there is no GPIO, PMU line or register to drive. Apple's own J81 driver works without it, so it cannot be a precondition of the ROM accepting HBPP on this board. Where the property exists (other boards) it is set to 1 around reset assert, around the HBPP detect and around `bootloadDevice`, and to 0 right after reset release (E, see the table in section 3). Do not add a made-up resource. The leading suspect in the brief is therefore ruled out; the cause is the bit order above.

## 3. Ordered sequence from power-up to the first firmware byte (answers Q1)

Delays are `IOSleep` milliseconds unless stated (E: the kernel thunk `0x23a3bd4` is called with the log text "delaying %d milliseconds" in `0xffffff8002fc5aac`; `0x23a3be0` is a microsecond delay, E from its use for the 10 us CS delay and the PIO polling loop). Class N1 (`AppleMultitouchN1SPI`) is the J81 class (E: personality `IOClass`); its vtable differs from Z2 only in the wake slot and the bootloader's `performCalibSeq`.

Start-up, `0xffffff8002fc074c` (vtable `+0x6e0`):

| Step | Action | Delay / wait | Evidence |
| --- | --- | --- | --- |
| 0 | reset line already asserted (iBoot leaves GPIO82 low); `downloadMode(1)` | unsupported, ignored | E |
| 1 | `setPowerEnabled(1)` `0xffffff8002fbbb64`: honour minimum power-cycle spacing | `0x788` returns 200 ms; sleep for the remainder since the last power-off | E (`0xffffff8002fc1488`) |
| 2 | power functions on, `0xffffff8002fbb9b4`: `function-power_ana` (D2207 `Lump` 0x20e = LDO14) first, then `function-power_ldo` (GPIO95 high) | none between them | E (off is the reverse: GPIO95 then LDO14) |
| 3 | power-up hook `0xffffff8002fc0c9c`: `function-enable_cs(1)` | **5 ms sleep before the call** | E |
| 4 | `function-clock_enable(1)` (KLCT, 32.768 kHz; 8 us internal settle) | none | E |
| 5 | wait | **15 ms** (`0x790` returns 15) | E (`0xffffff8002fc14dc`) |
| 6 | **N1 only: 2-byte `19 c1` ("REQ_WAKEUP")** full duplex, reply ignored, **while reset is still asserted** | **10 ms after** | E (`0xffffff8002fc5a08`) |
| 7 | `function-display_sync(1)` (GPIO55, mode 3) | none | E |
| 8 | reset release `0xffffff8002fc0b58(0)`: first **16-byte dummy transfer** `1a a1` + 7 x `18 e1` ("ensuring S_CLK is high"), full duplex, reply ignored | none | E (`0xffffff8002fc0d70`) |
| 9 | `function-reset` released (driven, not high-Z: `reset-deassert-high-z` is not in the personality), then `downloadMode(0)` | **15 ms** (`reset-deassert-delay`) | E |
| 10 | back in `finishStarting` | **15 ms** | E |
| 11 | **HBPP detect** `0xffffff8002fc1d10` (slot `+0x890`): `downloadMode(1)`, one **16-byte full-duplex** transfer `1a a1 18 e1 18 e1 18 e1 18 e1 18 e1 18 e1 18 e1`, `downloadMode(0)`. Success needs both the first and the second reply word (big-endian bytes 0-1 and 2-3) in `{18e1, 1aa1, 1f01, 4879, 4969, 4ad1, 4bc1}`; otherwise "Could not detect HBPP", power off, give up | n/a | E |
| 12 | bootload is started later from a timer (`0xffffff8002fb8df0`, `setTimeoutMS`), argument 15 ms in the power-on path | at least about 15 ms after step 11; exact path through the superclass tail call **U** | I |
| 13 | `MTSPIBootloader_Z2::bootloadDevice` `0xffffff8002fc3fb4` (shared by N1): `downloadMode(1)`; firmware (constructed packet, `0xffffff8002fc43c4`); proximity calibration; calibration; `performCalibSeq`; execute; `downloadMode(0)` | on failure `IOSleep(40)`; the owner retries the whole bootload up to 3 times, with no reset in between | E (`0xffffff8002fb8f88`) |
| 14 | firmware: **one transmit-only transfer** `transfer(buf, len, NULL, 0, 0)` of the whole constructed packet (PIO below 0x100 bytes or when DMA is disabled, DMA otherwise), then **immediately** the 2-byte ATN/ACK `1a a1` (separate transfer, reply read big-endian) which must equal `4b c1`; the pair is retried up to 5 times | no IRQ wait, no fixed delay between them; only the 10 us CS hold/setup of the controller | E |

What the driver waits for: **nothing on the IRQ/ATN line** in this phase (E: none of the functions above reads the interrupt). The host interrupt is enabled later, after the firmware is running ("enabling interrupts", `0xffffff8002fb898c` path). The boot IRQ edge that `touch-diag` waits for is not part of Apple's bootloader sequence; waiting for it adds a dependency Apple does not have.

Notes on the order versus `touch-diag`: Apple powers the rails (LDO14, then GPIO95) **before** enabling the 32 kHz clock and chip select; `touch-diag` enables the clock first. Apple sends the `19 c1` wake and the dummy frame while reset is asserted, and the detect frame (not an `ee ... ee` wake) is the first frame after release. The `ee 00 ... ee 00` 16-byte wake (`0xffffff8002fc5aac`) is used only in the report phase, and only when more than 100 ms have passed since the previous wake, followed by a 2 ms sleep; it is not part of boot.

## 4. Transfer helper semantics, DMA and framing (answers Q3 tail and Q4)

- **E:** `transfer(tx, txLen, rx, rxLen, 0)` is `AppleARMSPIDevice` vtable `+0x570` (`0xffffff8002671d88` builds an `AppleARMSPICommand` and queues it to the controller). One call = one chip-select frame: CS asserted, 10 us, all bytes, 10 us, CS released. Passing `rx = NULL, rxLen = 0` is transmit-only (the controller still clocks every transmit byte; the receive side is discarded). The final argument is an optional per-command struct; `0` selects the defaults above (E: the command copies three words from it only when non-NULL).
- **E:** the "DMA variant" is `+0x560` with a memory descriptor. The bootloader uses it only when its DMA flag (bootloader object `+0x58`) is set **and** the packet is at least 0x100 bytes (`0xffffff8002fc43c4`, `0xffffff8002fc4560`); the flag is cleared by the `mt-disable-fdldma` boot-arg (`DisableFDLDMA`). The SPI3 node has `dma-channels`, so a normal boot uses DMA for the 59,288-byte packet (I).
- **E:** framing is identical. DMA length is rounded up to a multiple of 4 (`(len + 3) & ~3`; for the unconstructed path `len + 16` rounded up); the 59,288-byte constructed packet is already a multiple of 4, so PIO and DMA send the same bytes, with no length prefix, padding or trailer from the transport. The same controller routine (`0xffffff8002900f64`) does CS handling, the 10 us delays, the word delay and the bit order for both paths.
- **E:** short ATN/ACK `1a a1` (2 B, reply taken from rx bytes 0-1 big-endian), long ATN (8 B, status in rx bytes 2-5), register write (16 B, ACK `4a d1`), execute (12 B), calibration request `1f 01` (2 B, then 65 ms) are unchanged from `j81-z2-n1-transport-framing.md`.
- **U:** the SPI source clock (nclk/pclk Hz) that turns 124 ns and 5000 ns into a divider and a word-delay count; the Linux S5L driver's `WORD_DELAY` is only written with 0 (patch 0007), so Apple's 5 us word delay is not reproduced by any current Linux path.

## 5. What the ROM answers (answers Q5)

- **E:** the only pre-firmware state check is the HBPP detect in section 3 step 11. It is a write-and-read of the same 16 bytes; there is no version read, no wake-first rule, no ATN wait. The accepted words are the seven above; `1f01` is also the calibration-request opcode word.
- **I:** the ROM's idle word is `0x1f01` (consistent with every recorded reply once bit order is corrected: `1f 01` repeated). `4b c1` is the post-data ACK and `4a d1` the post-register-write ACK; `18 e1` and `1a a1` are the data-header and ATN words (E: from the detect and ACK code).
- **E:** the all-zero reply to the dummy frame is expected: the dummy runs while reset is asserted.
- **I:** with correct bit order the detect frame should return `1f 01` (or another accepted word) in bytes 0-1 and 2-3. That, not an IRQ edge, is the success criterion for the next run, and it needs no firmware.

## 6. Corrections to existing notes

1. `touch-diag` mode 2 and "CFG 0xd" (`j81-touch-diagnostic.md`, `touch-diag.c` defaults): wrong. `0xd` is CTRL; the device mode is **0**, **LSB-first**, 8 bits.
2. 1.984 MHz ("124 x 16 kHz"): wrong. Cell 1 is a clock **period** (124 ns, about 8 MHz).
3. "Constant idle pattern of the boot ROM, cause unknown" (`2026-10-11-touch-upload-hardware-result.md`): the pattern is the valid HBPP idle word `0x1f01` read bit-reversed.
4. `function-enable_download` as the leading suspect: ruled out (section 2).
5. The unknowns "chip-select continuity" and "paused clock inside a long message" in the firmware spec are moot as the cause; Apple itself sends the packet as one DMA transfer.
6. 5000 and 10000 are SPI delays (word, CS), not touchscreen sizes. The raw `touchscreen-size-x/y` remain unrecovered.

## 7. Minimal changes to `boot/touch-diag.c` for the next hardware run

Order the experiments so each adds one variable; the first needs no firmware and no extra approval beyond the existing diagnostic run (it sends only the 16-byte detect frame that Apple sends).

1. **Bit order (the fix).** In `spi_open()` set `mode = (g_spi_mode & 3) | SPI_LSB_FIRST` (0x08) for `SPI_IOC_WR_MODE`, read it back, and change the readback check (`(rmode & 3) == mode`) to compare `(rmode & (3 | SPI_LSB_FIRST))` against the full requested value. Print the readback. The patched controller supports it (`mode_bits` includes `SPI_LSB_FIRST`; the S5L path clears the MSB-first bit for it). Keep 8 bits per word.
2. **Run A (single variable):** same as the 2026-10-11 runs but LSB-first, mode 2, 1.984 MHz. Expected: every reply now decodes as `1f 01 1f 01 ...` (aligned) instead of `f8 80` / `f1 01`.
3. **Run B:** add `--spi-mode 0` (Apple's mode). Expected the same aligned words. If the stream is aligned in mode 0 as well, stay in mode 0 from here on. Raise the rate to 8,000,000 only after A and B work (Apple's 124 ns period; U on the exact divider).
4. **Detect frame first.** After reset release wait 15 ms (existing) + 15 ms, then send `F_DUMMY` (the 16-byte `1a a1 18 e1 ...` frame, already in the file) as the first post-release frame and require bytes 0-1 and 2-3 in `{18e1, 1aa1, 1f01, 4879, 4969, 4ad1, 4bc1}`; print each as a big-endian word and a PASS/FAIL line. Remove the `ee ...` wake from the pre-firmware path (keep it only for later report-phase experiments). Do not require the boot IRQ edge before sending; log the edge, do not gate on it.
5. **Apple order and delays (optional, one commit):** order the unwind-safe sequence as reset asserted; LDO14 on, GPIO95 high (no delay between); 5 ms; clock enable; 15 ms; 2-byte `19 c1` full duplex then 10 ms; (display_sync pinmux if the flag is set); dummy frame; release reset; 15 ms; 15 ms; detect frame. The current clock-first order produced the boot IRQ and need not change for run A/B; the `19 c1` wake is the one new frame.
6. **`function-enable_download`:** no code. Log "unsupported on J81 (no property)".
7. **Firmware run (only after A/B pass and a separate go-ahead):** the existing single 59,288-byte message is already Apple's framing. Required deltas: LSB-first; send the packet transmit-only is fine either way; send `1a a1` immediately after (drop the 0/2/10/50/200/1000 ms schedule and the IRQ watching); success `4b c1`; retry packet + ACK at most 5 times as Apple does.
8. **Delays (only if A/B/7 still fail):** emulate Apple's 10 us CS hold by `delay_usecs = 10` on the last `spi_ioc_transfer`; for frames of at most 511 bytes the 5 us word delay can be emulated with one-byte transfers in a single message with `delay_usecs = 5` and CS held. For the 59 KB packet that needs a small `spi-apple.c` change (program `WORD_DELAY` = ceil(5000 ns x pclk) when `xfer->word_delay` is set) or a chain of messages whose last transfer has `cs_change = 1`; defer until needed.
9. **Tests:** extend `boot/test_touch_diag_frames.py` to assert the LSB flag in the mode byte, the readback comparison, and the accepted-word set; add a host test that bit-reverses `1f 01` bytes and checks the documented `f8 80` / `f1 01` observations.

Evidence for the central claim is therefore checkable without hardware: the byte-10 test and the bit-13 constant in `0xffffff8002900e10`, the `spi-version 1` constant table in `0xffffff8002900738`, and the accepted-word set in `0xffffff8002fc1d10`.
