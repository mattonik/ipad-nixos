# Native Z2 receive validation and transport audit, 2026-10-04

This follows the [touch bring-up audit](j81-touchscreen-bringup-offline.md).
The private preconstructed firmware packet is unavailable here. No iPad,
SPI transaction, PMIC write, private calibration or full kernel build was
used. This work validates Linux reference behavior; it does not establish
that J81 implements the same wire format.

## Exact source and refreshed groundwork

Inspected Hoolock
[`drivers/input/touchscreen/apple_z2.c`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/input/touchscreen/apple_z2.c)
at `6831bc701a6ce059e71e5aaa9488c9195bea6927`, 13,103 bytes, SHA-256
`de82c35ccbc760b0ad59376902a3fbcd06bf4843cb917d6f5b7ba874376ca347`.

The existing `0011` patch applied with default GNU patch but required fuzz 1
for three hunks. With `--fuzz=0`, three hunks failed. Its firmware-error
string also had a doubled backslash, emitting literal backslash-n.
The patch is regenerated against the exact pin so every hunk applies with
zero fuzz. It retains the three already intended bounds guards and both
match-table entries. The receive allocation now uses the same 4000-byte
constant as the length guard, preventing an independently edited limit.

Unlike the inactive OTP candidates, `0011` is already referenced by
`kernel/hoolock.nix`. This is a refresh of active build groundwork, **not** a
new inert candidate. There is still no J81 touchscreen child enabled by this
change. Existing built payloads are not rebuilt or replaced here; the laptop
must evaluate/build the refreshed patch before a hardware session.

## Actual native functions, synthetic interfaces

[`kernel/test_apple_z2_receive.py`](../kernel/test_apple_z2_receive.py)
requires the exact source hash, applies `0011` to a temporary tree with zero
fuzz, and compiles the actual original/patched definitions of:

- `apple_z2_parse_touches()`;
- `apple_z2_read_packet()`; and
- `apple_z2_upload_firmware()`.

Structures and protocol constants are extracted from the pinned source.
Host stubs represent SPI, firmware lookup and Linux input calls. They check
the read command's 16-byte size, marker, alternating counter and checksum.
They do not implement real bus timing, CS transitions, IRQs or input-core
semantics. Endian helpers assume a little-endian host and the harness refuses
other hosts. The native layout confirms 30-byte finger records and a
12-byte HBPP header struct, including its C tail padding.

| Check | Result / scope |
| --- | --- |
| All 65,536 device-advertised lengths | Refreshed driver rejects every rounded length above 4000 before the second SPI read; smaller lengths retain the original calculation |
| Original maximum length | Stub observes an oversized second read request; it deliberately does not emulate copying beyond the allocation |
| All 256 count-byte values | Complete synthetic records parse; an array one byte short is rejected before any slot reporting |
| Message sizes 0–23 | Return before reading the count/finger payload |
| Firmware sizes 0–7 | Refreshed uploader rejects before dispatching a blob or marking booted |
| One-byte original firmware | ASan separately reproduces an original header read beyond its allocation |
| Header-only version-1 firmware | Original and refreshed uploaders retain their existing success behavior; this is not proof such a file can boot a controller |
| SPI failure / wrong reply marker | Original error/ignore behavior retained; no second transfer after failed header exchange |

GCC warning-as-error compilation passes (baseline signed-comparison warnings
are suppressed). ASan/UBSan runs pass for the patched path; the separate
baseline short-firmware process fails with the expected heap-buffer-overflow.
LeakSanitizer was disabled because of the earlier environment restriction.
These checks are function-level evidence, not kernel ABI/build or J81
protocol validation. No claim is made about actual controller responses.

```sh
python3 kernel/test_apple_z2_receive.py --source /path/to/pinned/apple_z2.c
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_apple_z2_receive.py \
    --source /path/to/pinned/apple_z2.c --sanitize
python3 tools/check_offline.py --source /path/to/pinned/pcie.c \
    --z2-source /path/to/pinned/apple_z2.c
```

The runner now exposes `--z2-source`; all 16 source-enabled host scripts pass
with the two built-payload checks explicitly skipped. The runner still
performs no downloads or device access.

## Transport observations that remain separate gates

**ACK is not validated by this Linux reference.** Its blob transfer is
followed within one SPI message by a two-byte TX transfer `1a a1`. That
transfer has no RX buffer, so the driver cannot inspect returned ACK bytes.
The subsequent 20 ms IRQ-completion wait is deliberately nonfatal. This
must not be substituted for the older Apple N1 driver's response validation
when adapting the private `e118` preconstructed packet. Existing firmware
identity inspection remains `transport_ready: false`.

**Calibration length needs matching wire-format evidence.** The builder
advertises `round_up(cal_size, 4) / 4` words, but its allocation and trailing
checksum position use unrounded `cal_size`. For example, one calibration
byte produces a 17-byte blob using the observed 12-byte C header, while the
length field advertises a four-byte data area. Nonaligned counts can thus
produce odd total transfer lengths even though blob transmission requests
16-bit words. This is a source-derived inconsistency to investigate, not
proof that J81's private calibration has such a length or that adding zero
padding would match Apple. No calibration-layout change is made.

**Input interpretation deserves a later pass.** The reference reports the
orientation field via unsigned `le16_to_cpu()` while declaring its input
axis range as -32768 through 32767. Source review alone does not establish
J81's orientation encoding; record captures should determine signedness
before a J81-specific mapping is introduced. This refresh preserves existing
field interpretation and does not infer coordinates from display resolution.

**Platform and wire gates remain.** SPI mode/rate, GPIO electrical polarity,
D2207 analog rail control, PMGR KLCT gate mapping and display-sync handling
still require matching Apple provider code and device evidence. A registered
SPI master and passing host tests do not justify creating an operational
touchscreen child or uploading the preconstructed packet.

Next driver research can validate calibration construction against a matching
public implementation or privately supplied Apple disassembly/captures. The
next hardware observation should continue the existing platform/power plan;
this audit introduces no transaction recipe or guessed register writes.
