# Z2 ACK and calibration reference comparison, 2026-10-04

Follow-up to [native Z2 validation](j81-z2-native-validation.md). No hardware,
private calibration, firmware upload, GPIO/PMIC write or Nix build was used.
The result is an executable public-reference comparison and a narrower evidence
request, not a J81 transport implementation.

## Sources and applicability

| Pinned primary source | Useful evidence | Limit for J81 |
| --- | --- | --- |
| [openiBoot Z2 source](https://github.com/iDroid-Project/openiBoot/blob/866562fdb1cfd019bcd77885c80fbf0af65d5c15/plat-s5l8900/multitouch-z2.c), `866562fdb1cfd019bcd77885c80fbf0af65d5c15` | Actual ACK reader, constructed-packet upload and calibration builder | S5L8900 platform, different calibration addresses; not Apple N1/J81 proof |
| [iPad touchscreen capture/replay project](https://github.com/lemonjesus/ipad-touch-screen/tree/1f8a12e562c358356dfa171e3989f7bc53e37ace), `1f8a12e562c358356dfa171e3989f7bc53e37ace` | Native-boot transaction capture and replay in `training/training.c` | iPad 3/A5X; replayed board transactions do not supply a universal calibration builder |
| [Hoolock iPad 7 touch notes](https://github.com/Pauli1Go/HoolockLinux-bringup-docs/blob/c9d02dbcbb37d73cffb0ce048b03308c6416d8db/docs/touch.md), `c9d02dbcbb37d73cffb0ce048b03308c6416d8db` | Author-reported J172/A10 BCM15900B0 bring-up, SmartIO DMA and board-specific lifecycle | Documentation, not an executable source implementation in this checkout; clocks, GPIOs, HBPP generation and controller differ |

The previously reviewed Hoolock `apple_z2.c` remains pinned to
`6831bc701a6ce059e71e5aaa9488c9195bea6927`. Its two-byte `1a a1`
transfer has no RX buffer and its IRQ wait is nonfatal. Those facts establish
why copying its completion behavior is insufficient for an ACK-checking port.

## What the older implementation actually checks

`performHBPPATN_ACK()` consumes attention, with a 1000-microsecond source
timeout, then performs a two-byte full-duplex `1a a1` exchange. It decodes
`rx[0] << 8 | rx[1]`. `loadConstructedFirmware()` accepts only `0x4bc1`,
retrying at most five times. Thus response bytes `4b c1` succeed in that
implementation; `c1 4b` do not. This is a **candidate J81 observation**, not
permission to interpret every J81 attention event as successful upload.

The long response helper transmits `1a a1 18 e1 18 e1 18 e1` and combines
response bytes 2/3 as the low word and 4/5 as the high word, each word most
significant byte first. Its attention wait is unbounded. Do not import that
wait, retry policy or timing into a new driver without lifecycle evidence.
Host stubs verify byte decoding and retry decisions, not electrical timing.

## Calibration layout in the legacy source

The builder emits the following **core packet bytes in its output buffer**.
This table is not a proposed J81 on-wire layout; SPI word size/controller
byte ordering and chip-select boundaries must be established independently.

| Core offset | Contents |
| --- | --- |
| 0–1 | `30 01` |
| 2–3 | Word count; low byte is `dataLen / 4`; high-byte expression uses `>> 10` after division by four |
| 4–7 | Address bytes in order bits 8–15, 0–7, 24–31, 16–23 |
| 8–9 | Sum of bytes 2–7, high byte then low byte |
| 10 onward | Data with every adjacent byte pair exchanged |
| After data, four bytes | Data byte sum, low 16-bit word first, high byte first inside each word |

`loadCal()`/`loadProxCal()` prepend `18 e1`, then send aligned chunks capped
at `0x3f0` (1008) bytes. Total buffer length is chunk length + 16. Their
destinations start at `0x400200` and `0x400180`, respectively; do not transfer
these addresses to J81 or to the Linux reference's `0x10009000` destination.

Two limitations prevent treating this as a ready-made padding fix:

- The unusual high count-byte shift is harmless in the observed calibration
  caller domain (at most 252 words, so that byte is zero), but is not a
  validated encoder for larger packets. The 59,288-byte J81 preconstructed
  asset must not be rebuilt through this function.
- Callers round the remaining length upward while keeping the original data
  pointer. The source does not establish that the backing asset has readable,
  correctly populated padding. An unaligned synthetic allocation could be
  overread. The harness uses explicitly allocated, aligned synthetic input;
  it does not validate those callers' buffer ownership.

The Linux calibration builder uses an observed 12-byte C header, unrounded
data allocation/checksum placement, and a rounded advertised word count.
Legacy code instead uses an explicit ten-byte core header plus two-byte
wrapper. Equal header-plus-wrapper size is not evidence of equal meaning.
In particular, neither implementation proves the padding values, checksum
span or transaction structure required by J81's private Apple provider.

## Reproducible offline validation

[`kernel/test_openiboot_z2_reference.py`](../kernel/test_openiboot_z2_reference.py)
checks the source SHA-256
`5385aaa7463e6ac5c927a3a848256af2c1992e7b80fa064d95bd56b85f38d883`,
extracts four actual reference functions into temporary host C, and compiles
them with GCC. No third-party implementation is vendored and no private
asset is used. The functions are tested with synthetic interfaces:

- All 252 positive, four-byte-aligned sizes through the legacy caller cap;
  count/address byte order, header/data checksum spans and payload swapping.
- First/third-attempt success, swapped ACK rejection, five-attempt failure
  without attention, and long response word decoding.

```sh
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_openiboot_z2_reference.py \
  --source /path/to/openiBoot/plat-s5l8900/multitouch-z2.c --sanitize
python3 tools/check_offline.py \
  --source /path/to/pinned/pcie.c --z2-source /path/to/pinned/apple_z2.c \
  --openiboot-source /path/to/openiBoot/plat-s5l8900/multitouch-z2.c
```

All 17 source-enabled scripts passed with ASan/UBSan enabled; Image and USB
payload checks were explicitly skipped because built artifacts are absent.
These results cover host behavior, not a kernel build or working touchscreen.

## Next evidence that would resolve the driver choices

Use the existing J81 platform/power plan first. Once a matching native-boot
capture or Apple N1 disassembly is available, record these relationships:

1. Whether `1a a1` receives `4b c1` after the preconstructed upload, and how
   attention, SPI transfer and response validation relate in time.
2. SPI word size, mode, rate, controller byte ordering and chip-select
   continuity across payload and response transfers.
3. A calibration packet's complete header, destination, advertised length,
   actual data/padding length, checksum span and wrapper position. Keep raw
   calibration and device identifiers private; publish only sanitized rules.
4. Which initialization stage produces the final calibration-completion
   response and whether failures require reset rather than retransmission.

The iPad 3 replay project supports capture as a practical investigation
strategy. The iPad 7 report reinforces that provider resources and DMA setup
are board-specific. Neither supplies J81's missing analog-rail, KLCT, SPI or
display-sync mapping. No touchscreen child or new hardware recipe is enabled.

An [offline capture analyzer](j81-touch-capture-analyzer.md) now checks this
limited legacy profile and compares normalized transactions without exposing
payload bytes. It includes synthetic tests; a profile match is not J81 proof.
