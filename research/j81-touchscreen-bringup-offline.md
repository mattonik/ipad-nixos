# J81 touchscreen bring-up: offline evidence and safe next step

Date: 2026-09-25

## Scope and result

This is an offline review of the captured J81 ADT, the existing iPad5,3 iOS
8.1 kernelcache/Ghidra project, the pinned Linux source, and this repository's
touch work. No build was run, no live device was accessed, and no hardware
state was changed.

The evidence is strong enough to describe the transport and most resources,
but not to bind the touchscreen safely yet. J81 uses Apple's N1/Z2-family
packet and firmware protocol over SPI3. Mainline `apple_z2` is the right
protocol and input-framework reference, while the local S5L SPI controller
port supplies the bus. The upstream driver does not sequence J81's analog
rail, enable GPIO, 32.768 kHz clock, or display-sync GPIO. Its receive path
also trusts two lengths supplied by an unproven controller. A direct J81
binding would therefore be premature.

Labels below keep fact and interpretation separate:

- **E — evidence:** directly observed in an artifact or authoritative source.
- **I — inference:** the best interpretation of several observations.
- **U — unknown:** required information that the reviewed material does not
  establish.

## Evidence base

| Artifact | Identity | What it establishes |
|---|---|---|
| Captured J81 ADT | SHA-256 `cf743765e66a1a5b45cbf4e18c0e5ae21454bb1cb678b66e7007e2db04f5b6c2` | SPI3 and touch-node resources listed below. The private calibration value was inspected only for structure and is not reproduced here. |
| iPad5,3 iOS 8.1 kernelcache | build `12B410`; SHA-256 `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf` | `AppleMultitouchSPIJ82` personality and `AppleMultitouchN1SPI` implementation. |
| Existing Ghidra project | full prelinked image; `AppleMultitouchSPI` load address `0xffffff8002fb7000`, size `0x19000` | Bootloader calibration and platform-resource callbacks described below. |
| Pinned Hoolock Linux source | configured by [`kernel/hoolock.nix`](../kernel/hoolock.nix) | Exact `apple_z2` and DT-binding behavior reviewed. |
| Repository patches and prior captures | [`docs/plans/2026-09-09-j81-touch-spi3.md`](../docs/plans/2026-09-09-j81-touch-spi3.md) | S5L SPI port, built-DTB checks, and completed SPI3 registration observation. |

The ADT and kernelcache are private/local evidence. Hashes make the findings
reproducible without committing device-specific blobs or calibration data.

## Bus and wire protocol

### SPI controller

- **E:** The ADT node is `spi3`, compatible with Apple's
  `spi-1,samsung`. Its register tuple decodes to AP physical address
  `0x20a08c000`, length `0x4000`; its AIC interrupt is 155; its clock-gate ID
  is 77; and CS0 is AP GPIO51.
- **E:** The touch child selects chip select 0. The parent has
  `#address-cells = <1>` and `#size-cells = <7>`, so the child's first
  `reg` cell is the SPI chip select. The remaining seven cells are Apple
  private data, not a Linux MMIO range.
- **E:** The locally patched DT enables this controller as
  `apple,s5l8960x-spi`, with the decoded register, interrupt, power domain,
  and GPIO51 pinmux. The completed TOUCH-1 observation found the real J81
  master at `20a08c000.spi/.../spi0`, stable for more than four minutes,
  without a touch child or transaction.
- **E:** The local controller support comes from Hoolock's S5L experiment,
  with fixes recorded in
  [`0007-spi-apple-add-s5l8960x-support.patch`](../kernel/patches/0007-spi-apple-add-s5l8960x-support.patch).
  This is project/Hoolock code, not support present in upstream `spi-apple.c`.
- **U:** The J81 ADT has no explicit touch `spi-frequency`, and this review
  did not establish J81's CPOL/CPHA mode. Values in its
  private packed `reg` cells must not be reinterpreted as a frequency.
  The 11.5 MHz in the upstream Touch Bar DT example and the 8 MHz on an
  unrelated Mesa node are not J81 evidence.

### Device identity and framing

- **E:** The ADT compatible is `multi-touch,j82`. Apple's matching
  personality is `AppleMultitouchSPIJ82`, whose I/O class is
  `AppleMultitouchN1SPI` and provider is `AppleARMSPIDevice`.
- **E:** That personality supplies reset-deassert delay 15, parser type 1,
  parser options 16, touch-size ID 3, and firmware merge personality
  `C1F15,2`.
- **I:** This is an N1-era member of Apple's Z2 protocol family. Board and
  repair sources identifying the physical controller as BCM5976 are useful
  secondary evidence, but neither the ADT nor Apple class name proves the
  exact commercial silicon marking. The Linux binding should follow the
  Apple personality/protocol evidence rather than depend on that name.
- **E:** The upstream Linux read command is 16 bytes, begins with `0xeb`,
  carries an alternating counter/parity byte, and ends in a checksum based
  on the command and counter. A full-duplex command exchange expects reply
  marker `0xe1`; the reply provides a little-endian payload length, and the
  driver performs a second SPI read for the payload plus framing, rounded to
  four bytes.
- **E:** The Linux parser reads the finger count at message offset 16 and
  30-byte packed finger records from offset 24. Finger states 3 and 4 are reported
  as active multitouch contacts.
- **E:** Strings and references in Apple's N1 implementation show explicit
  handling of bad headers, checksums, and frame lengths. This independently
  supports the protocol relationship, but it does not prove that every J81
  packet field is identical to the newer Linux-supported devices.

## Reset, power, interrupt, clock, and firmware dependencies

| Resource | Evidence | Bring-up implication |
|---|---|---|
| Reset | **E:** ADT `function-reset` is AP GPIO82. Apple's code asserts reset before teardown and deasserts it only after platform setup; the personality supplies delay 15. | **I:** The local DTS proposal maps it active-low, consistent with Linux Z2's logical assert/deassert use. The Apple GPIO-provider semantics should be decoded before treating that as electrical polarity. |
| Interrupt | **E:** ADT interrupt GPIO is AP GPIO84, separate from SPI3's AIC IRQ155. Linux Z2 waits for a boot interrupt after reset release. | **I:** Falling-edge is a reasonable Linux mapping from the current plan and binding example, but the ADT bytes establish the line more firmly than the trigger polarity. Confirm the trigger before enabling it. |
| Chip select enable | **E:** ADT `function-enable_cs` is AP GPIO51. Apple calls the CS-enable function during platform power transitions and adds a short delay on enable. GPIO51 is also SPI3 CS0 and its peripheral pinmux was observed. | **U:** Whether Linux pinctrl alone reproduces the Apple callback at every transition needs a state-machine comparison. |
| Analog rail | **E:** ADT `function-power_ana` points to D2207 with Apple `Lump` argument `0x20e`. Existing PMIC decoding maps this to LDO14. Its voltage register `0x0398` was previously read as `0x14` (6.0 V configured); enable register `0x0084` was `0x00` (rail off). | **I:** Treat it as enable-only and preserve voltage. Linux has no J81 D2207 regulator provider for this rail; the repository's D2207 code only reports charger state. Do not issue a raw PMIC write from the touchscreen driver. |
| Digital/secondary enable | **E:** ADT `function-power_ldo` is AP GPIO95 despite the name. Existing baseline observation found it unclaimed. Apple's power helper sequences the analog source and this GPIO, reversing the sequence at power-off. | **U:** Electrical polarity and required inter-rail delay need confirmation from the Apple GPIO-provider path. |
| 32.768 kHz clock | **E:** ADT `function-clock_enable` refers to the PMGR/KLCT tuple `[8, 100, 32768]`: enable settle, disable settle, and target rate. The decoded PMGR divider model derives 32.768 kHz from 24 MHz. | **U:** The exact touch KLCT gate-table index is still missing. There is no Linux provider for this old PMGR clock. A guessed raw register write is unsafe. |
| Display sync | **E:** ADT `function-display_sync` is AP GPIO55. Apple's platform code enables and disables the callback around device operation. The line was unclaimed at the existing baseline. | **U:** Its electrical waveform and whether boot/firmware upload can succeed without it are not established. Do not assume it is optional merely because upstream Z2 ignores it. |
| Internal ASIC setup | **E:** Apple's `MTSPIBootloader_N1::performCalibSeq` reads chip version at `0x10008ffc`, programs reference-clock and calibration registers, writes `0x10003058 = 6`, conditionally programs `0x10003518 = 1`, and then requests calibration. Personality addresses also include firmware execute `0x10003400` and calibration download `0x10009000`. | These are controller-internal SPI addresses, distinct from the SoC PMGR/KLCT clock. They belong in a validated N1 firmware/calibration sequence, not platform MMIO code. |

The Ghidra call graph supports this broad order: set up CS and the platform
clock, perform power/setup callbacks, enable display sync, then release reset.
The power callback itself enables the D2207 analog source before GPIO95 and
reverses those operations at shutdown. Several calls are virtual dispatches,
so this is evidence for ordering classes rather than a complete register-level
recipe.

### Firmware and calibration

- **E:** The upstream binding requires `interrupts`, `reset-gpios`,
  `firmware-name`, and raw `touchscreen-size-x/y` in addition to the SPI
  compatible and standard SPI peripheral properties. Its optional
  `apple,z2-cal-blob` is limited to 4096 bytes.
- **E:** Upstream `apple_z2` calls `request_firmware()` and expects a `Z2FW`
  version-1 container. Its commands initialize the bootloader, transfer blobs,
  and deliver calibration in an HBPP `0x3001` record with target address and
  checksums. Transfers switch between 8-bit and 16-bit words as required.
- **E:** The upstream driver describes the upload as volatile: an interrupted
  upload can break that boot attempt, but the controller has no nonvolatile
  storage and resets on the next boot.
- **E:** The J81 ADT contains a private `multi-touch-calibration` blob. The
  Linux binding also permits an `apple,z2-cal-blob` supplied by the
  bootloader. This repository must not publish the captured per-device data.
- **E:** A private, read-only extraction of the exact iPad5,3 iOS 8.1
  `12B410` filesystem recovered
  `usr/share/firmware/multitouch/J81.mtprops` (SHA-256
  `4feb5081f071760d37b7cf8802b729f6bd36f48eb8a7890222c21ea2b1e5d1dc`).
  Its `C1F15,2` entry has `PreconstructedBootloadPacketType = "Z2"`, version
  `0x0381.bin`, reset interval `432000`, and a 59,288-byte `Constructed
  Firmware` payload. The payload was copied only to private scratch space;
  its SHA-256 is
  `9948ce32f7ec68507d58a01392fc2ac8add5bfeace4c88310da2107b1e2d54e2`.
- **E:** That payload starts with little-endian marker `0xe118`, is aligned to
  four bytes, and contains no `Z2FW` magic. It is therefore an Apple
  *preconstructed* Z2 boot packet, not a Linux `apple_z2` version-1 firmware
  container.
- **E:** The matching ship `AppleMultitouchSPI` code loads `Constructed
  Firmware` separately from `Firmware`. Its Z2 bootloader transmits the
  constructed value as one packet and checks the bootloader response; the
  alternate unconstructed path creates `0xe118` packets in chunks. This
  confirms the distinction is executable behavior, not a metadata label.
- **I:** The recovered asset is the correct firmware input for J81 research,
  but current upstream `apple_z2` cannot consume it directly. Do not wrap it
  in a guessed `Z2FW` header or send it to hardware. A small N1/Z2 transport
  adaptation must first reproduce Apple's packet and acknowledgement rules.
- **U:** Calibration wrapping, coordinate maxima, SPI rate and the PMGR clock
  gate remain unresolved. Display resolution is not a substitute for the
  controller's raw `touchscreen-size-x/y`, and the ADT's private values `5000`
  and `10000` are not established as dimensions.

### Callback argument semantics confirmed 2026-09-25

Fresh decompilation of the exact iPad5,3 driver resolved how the platform
callbacks are invoked, while leaving their provider-level electrical polarity
separate:

- `function-clock_enable` passes literal `3` in its third argument to enable
  the KLCT handler, and passes a zero first argument to disable it. This
  matches the earlier KLCT arithmetic result but does not reveal its fixed
  PMGR gate-table index.
- `function-display_sync` uses the same enable/disable argument convention.
- `function-enable_cs` passes its requested value through the callback and
  waits 5 microseconds before enabling it. Linux's verified SPI3 pinctrl
  establishes the CS peripheral mux, but this does not prove the callback is
  redundant during power transitions.
- `function-reset` receives the driver’s logical asserted/deasserted value
  directly. The Apple GPIO provider’s mapping from that logical value to the
  electrical level is still not recovered, so the current active-low DTS
  draft remains an inference rather than a confirmed electrical fact.

## Linux driver applicability and hazards

| Component | Applicability | Gap |
|---|---|---|
| Local S5L `spi-apple` port | Required bus controller and already proven to register without a child. | No J81 slave transaction has been observed; rate and mode still need device evidence. |
| Mainline `apple_z2` | Best starting point for Z2 framing, volatile firmware upload, and Linux multitouch reporting. | Upstream matches only `apple,j293-touchbar` and `apple,j493-touchbar`; it does not implement the J81 resource sequence or prove N1 packet compatibility. |
| Local `apple,j81-touchscreen` match patch | Avoids a known probe crash by adding the compatible to both OF and SPI ID tables. `apple_z2_probe()` dereferences `spi_get_device_id(spi)->driver_data`. | It is inert groundwork without a child node and does not make J81 operational. |
| Generic regulator/clock/GPIO frameworks | Appropriate shape for modeled supplies, clock, reset, and interrupt. | A D2207 LDO14 provider and old-PMGR KLCT provider/mapping do not yet exist; display sync has no upstream Z2 representation. |

Three input-validation checks are prerequisites for any J81 traffic:

1. **E:** `apple_z2_read_packet()` allocates a 4000-byte receive buffer but
   trusts the device-reported packet length when issuing the second
   `spi_read()`. It must reject a length larger than the buffer before that
   transfer.
2. **E:** `apple_z2_parse_touches()` trusts the device-reported finger count.
   It must prove that offset 24 plus `nfingers * sizeof(struct
   apple_z2_finger)` fits inside the received message before parsing.
3. **E:** `apple_z2_upload_firmware()` reads the fixed firmware header before
   it has proved that the supplied firmware file is large enough to contain
   that header.

These are memory-safety issues when trying an unsupported protocol variant,
not merely malformed-touch reporting. Apple's older driver checked equivalent
frame bounds. Binding the current local match to a child “to see what happens”
would immediately begin reset/boot/upload behavior and expose these unchecked
paths.

### Validation hardening completed 2026-09-25

The existing J81 groundwork patch,
[`0011-touchscreen-apple-z2-add-j81.patch`](../kernel/patches/0011-touchscreen-apple-z2-add-j81.patch),
now applies all three checks before it adds the J81 match:

- it names the existing 4000-byte allocation and rejects a larger
  controller-advertised read;
- it requires a complete fixed touch header, then rejects a finger count that
  cannot fit in the received message; and
- it rejects a firmware file shorter than `struct apple_z2_fw_hdr` before
  reading its magic or version.

This is deliberately the smallest shared fix: it protects the normal Touch
Bar path as well as a future J81 node, and it neither changes the wire
protocol nor starts a touch transaction. The patch was dry-run and applied
against the exact pinned Hoolock 7.3 source; a source-level assertion checked
that all three guards and both J81 match-table entries were present. No kernel
build was run in this research pass.

As of 2026-09-25, Linux `master` still has the same unbounded packet read,
unbounded finger walk, and short-firmware-header read. This is independent
confirmation that the local hardening is not redundant with a newer upstream
driver revision.

## Safest next experiment

The next experiment should remain **offline and read-only**:

1. Write a host-only parser for the recovered preconstructed Z2 packet. It
   must validate the `0xe118` framing and Apple acknowledgement assumptions
   from the disassembly before any Linux transport code is considered.
2. Recover the J81 SPI mode/rate, raw X/Y maxima, calibration envelope, and
   the missing KLCT gate index from Apple artifacts. Treat each as unresolved
   until two independent observations agree where possible.
3. Have the build owner compile the already-added validation patch, then
   exercise the resulting driver with truncated, oversized, and maximum-length
   synthetic frames before creating a J81 DT child. This neither requires a
   device payload nor touches hardware.

This resolves the largest unknowns with zero device risk. Repeating SPI3
registration alone would add little because TOUCH-1 already proved it.

After that offline gate passes, the smallest useful hardware experiment is a
dedicated diagnostic path in a separate RAM-only payload: begin with reset
asserted; enable only resources whose polarity and mapping have been proven;
release reset once; wait with a hard timeout for GPIO84's boot interrupt; make
no SPI transfer and upload no firmware; then assert reset and unwind resources
in reverse order. It must not run until the KLCT index, GPIO polarities,
interrupt trigger, and power order are resolved. The result should be only
“boot interrupt observed/not observed” plus resource cleanup evidence.

## Authoritative code references

- [Linux Apple Z2 touchscreen driver](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/apple_z2.c)
- [Linux Apple Z2 Device Tree binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/input/touchscreen/apple%2Cz2-multitouch.yaml)
- [Linux Apple SPI controller driver](https://github.com/torvalds/linux/blob/master/drivers/spi/spi-apple.c)
- [Hoolock S5L SPI experiment used by this repository](https://github.com/HoolockLinux/linux/commit/c065201fe71ed16efcb14569b5b40ef81343a70b)
