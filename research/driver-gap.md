# Driver gap analysis: iPad Air 2 (J81 / T7001)

Updated 2026-09-08 after reviewing the repository, the pinned Hoolock Linux
source, current upstream Linux, Hoolock's test branches, Corellium's Sandcastle
drivers, and the SoMainline J82 Apple Device Tree (ADT).

The implementation sequence, exact hardware map, tests and source links are in
[the current driver bring-up plan](../docs/plans/2026-09-08-ipad-air2-driver-bringup.md).

## Evidence boundary

The target is a Wi-Fi J81. The most complete public T7001 ADT inspected here is
J82, its cellular sibling. Its bus addresses, GPIO descriptors and device names
replace earlier teardown guesses, but every new J81 DT node must be checked
against a live J81 ADT dump first. Apple firmware, calibration, NVRAM and device
identifiers stay outside Git.

## Current baseline

- The historical Linux 5.19 route boots fully and reaches a visible shell.
- Historical DWC2 gadget networking receives host packets but cannot transmit
  them back through the bulk-IN endpoint -- this remains true only for the
  historical kernel; see below.
- **2026-09-08: resolved.** Hoolock Linux 7.3-rc1 at `6831bc7` booted
  completely on its first hardware attempt via `m1n1-hoolock-control`, and
  USB gadget networking works bidirectionally (0% ping loss, working
  telnet, real interactive shell access over the network). Full transcript
  in `docs/software-only-control.md`'s "Round 10."
- Apple PMIC RTC and backlight are hardware-verified as of the same
  session: RTC set the system clock from real hardware time; backlight
  physically dimmed the screen on command.
- Buttons remain DT-wired and built in, awaiting hardware validation.

## Corrected driver matrix

| Subsystem | Hardware/interface | Linux status | Actual gap | Next action |
| --- | --- | --- | --- | --- |
| CPU/SMP | A8X / ARM64 | Boots all CPUs | None for current milestone | Preserve known boot path |
| Interrupts | Apple AIC | Working during boot | None observed | Preserve |
| GPIO/pinctrl | Apple GPIO | Working during boot | New peripheral pins absent | Add only from live ADT evidence |
| Display | Bootloader framebuffer | Visible Linux console | No native A8X display/GPU stack | Retain simplefb |
| USB gadget | T7001 PHY + DWC2 | **Resolved 2026-09-08** on the Hoolock kernel: bidirectional networking works | None -- historical kernel's TX stall doesn't apply, real DMA works | Done; USB networking is the live channel now used for further hardware validation |
| Buttons | GPIO 0/1/92/93 | Driver/config/DT present | Physical test missing | Verify input events |
| RTC | Apple D2207 PMIC child | **Hardware-verified 2026-09-08** | None | `rtc-apple-pmic` registered as `rtc0`, set system clock from real hardware time (`hwclock -r` matched actual date), confirmed live over the newly-working USB network link |
| Backlight | Apple D2207 PMIC child | **Hardware-verified 2026-09-08** | None | `echo 200 > brightness` physically dimmed the screen, visually confirmed by the user, then restored to 1627/2047; confirmed live over the USB network link |
| Bluetooth | BCM4350-family radio over UART3 | `hci_bcm` and HCI UART BCM enabled | UART3 DT, wake, power and local firmware | First new peripheral after USB |
| Battery | TI BQ27540-family over HDQ/UART5 | bq27xxx core exists | Generic W1-UART has the wrong signaling; no serdev transport/DT | Reuse core behind a small HDQ serdev frontend |
| Touch | Apple `multi-touch,j82` / BCM Z2 family over SPI3 | Z2 parser/uploader exists for Mac Touch Bars | Old-SoC SPI variant, J81 binding, power, firmware and calibration | Prove SPI3 before adapting touch |
| Wi-Fi | BCM4350 over T7000 PCIe port 1 | brcmfmac PCIe supports BCM4350 | T7000 PCIe host/DT/power path missing; wireless config disabled | Port/enumerate PCIe, then enable brcmfmac |
| Sensors | Mostly behind the M8 coprocessor | No identified usable path | Inventory/protocol unknown | Defer |
| Audio | Apple DMA/codec path | No complete A8X stack | Controller, codec and routing work | Defer |
| GPU | PowerVR GXA6850 | No A8X platform integration | Major reverse engineering | Defer |
| NAND/cameras/Touch ID | Apple proprietary paths | No usable stack | Large storage/ISP/SEP gaps | Outside RAM-only milestone |

## What the kernel update changes

The Hoolock branch is the right base because it already carries the T7001 USB
PHY/DWC2 work, A8/A8X platform support, Apple PMIC RTC/backlight, Apple SPI
framework code and the old-Apple DART variant. The pinned revision was the
current `hoolock` tip at review time. Moving to a different generic Linux tag
does not add J81 Bluetooth, battery, SPI/touch or T7000 PCIe wiring.

Hoolock's `tests/spi` and `tests/kat-spi` branches contain useful old-controller
SPI work. They are experimental and should be reduced to the S5L8960X register
layout and quirks rather than merged wholesale. Its `tests/bluetooth` branch is
for T8015/BCM4349; only its integration patterns are relevant to J81.

## Bluetooth: closest new peripheral

The J82 ADT identifies UART3 at `0x20a0cc000`, IRQ 161, TX GPIO14, RTS GPIO32,
host-wake GPIO164, PMU power GPIO2 and 3 Mbaud. Current Hoolock config already
enables `BT`, `BT_HCIUART`, and `BT_HCIUART_BCM`; upstream `hci_bcm` has the
`brcm,bcm43540-bt` family match.

Add UART3 and the serdev child first without a shutdown GPIO. The bootloader may
leave the module powered, allowing the HCI path to be proven without guessing
PMIC registers. If it is off, the real next dependency is a D2207 PMIC GPIO
provider or narrowly scoped power sequence. Hoolock has a PMIC regmap parent but
no GPIO provider. Corellium's PMIC GPIO code demonstrates the shape of such a
driver for another PMIC; its register offsets are not portable to D2207.

## Battery: use the right wire protocol

The J82 ADT identifies a BQ27540-family gauge below UART5 at `0x20a0d4000`, IRQ
163, with the battery SWI/HDQ line on GPIO34. This resolves the old “unknown
pin” note.

The enabled upstream `w1-uart` path cannot drive this device correctly: it
generates standard 1-Wire timings. Corellium's public driver demonstrates the
working HDQ-over-UART transport at 57,600 baud with two stop bits, break/pulse
signaling, and `0xfe`/`0xc0` encoded bits. The maintainable implementation is a
small serdev transport that reuses Linux's bq27xxx core rather than copying
Corellium's standalone power-supply layer. Read `DEVICE_TYPE` on hardware
before mapping ADT's `bq27540` name to an upstream bq27xxx chip table.

## Touch: controller before protocol

J82 places the multitouch device on SPI3 at `0x20a08c000`, IRQ 155. Its signals
include chip select GPIO51, touch IRQ GPIO84, display sync GPIO55, reset GPIO82
and LDO GPIO95. Analog power is a PMU resource whose D2207 programming is still
unknown.

Current `apple_z2` supplies a useful firmware uploader and frame parser, but its
bindings cover Mac Touch Bars. Current Hoolock's normal branch lacks the
S5L8960X SPI controller variant needed here. Clean and test that controller
from the Hoolock SPI experiment first. Only after repeatable SPI transfers
should the Z2 driver receive an iPad compatible, live-ADT calibration, locally
extracted firmware and the verified power sequence.

## Wi-Fi: PCIe host work precedes brcmfmac

The J82 ADT calls the endpoint `wlan-pcie,bcm4350`. It is attached to T7000
PCIe port 1 at 2.5 GT/s with wake GPIO165, CLKREQ GPIO174, PERST GPIO179 and a
DART at `0x602002000`/IRQ216. UART2 is a control/sideband path, not an SDIO
data bus. This invalidates the repository's previous BCM4354/SDIO plan.

Upstream brcmfmac already maps BCM4350 PCIe firmware. The Hoolock tree also
contains that source, but the current kernel config does not enable CFG80211,
BRCMFMAC or BRCMFMAC_PCIE. Enabling them now would create no device because
the T7000 PCIe host is missing.

Port the host first, using the A8X ADT tunables. Upstream `pcie-apple.c` is the
preferred integration point if its controller model fits. Corellium's older
`pcie-hx.c` provides register and sequencing evidence, but its H9P hard-coded
tunables cannot be reused on A8X. Add the DART and only port 1, prove stable
PCI config-space enumeration, then enable brcmfmac and supply locally extracted
`brcmfmac4350-pcie` firmware/NVRAM.

## Implementation order

1. Boot and measure the existing Hoolock ECM payload.
2. Validate buttons, RTC and backlight.
3. Add J81 UART3 Bluetooth DT and prove `hci0`; add PMIC control only if needed.
4. Add the HDQ serdev transport and UART5 gauge node.
5. Clean S5L8960X SPI support and prove SPI3; then adapt Z2 touch.
6. Port T7000 PCIe/DART, enumerate BCM4350, then enable its wireless stack.

Each phase has exact acceptance criteria and rollback guidance in the linked
bring-up plan. Audio, native display/GPU, NAND, cameras, Touch ID and sensor-hub
support remain outside this milestone.

## Primary sources

- [Hoolock A8/A8X features](https://github.com/HoolockLinux/docs/blob/master/features/A8.md)
- [Hoolock Linux](https://github.com/HoolockLinux/linux/tree/hoolock)
- [SoMainline J82 ADT](https://github.com/SoMainline/adt_collection/blob/master/a8/J82.adt)
- [Linux brcmfmac PCIe](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)
- [Linux Broadcom HCI UART](https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_bcm.c)
- [Linux Apple PCIe](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c)
- [Linux Apple Z2 touch](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/apple_z2.c)
- [Corellium HDQ-UART gauge](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/bq27545-battery-hdquart.c)
- [Corellium old-Apple PCIe](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/pci/controller/pcie-hx.c)
- [Corellium old-Apple SPI](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/spi/spi-hx.c)
