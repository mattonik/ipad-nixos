# iPad Air 2 driver bring-up plan

Date: 2026-09-08

Target: iPad Air 2 Wi-Fi, J81 / T7001 (A8X)

Kernel candidate: Hoolock Linux 7.3-rc1, commit
`6831bc701a6ce059e71e5aaa9488c9195bea6927`

## Decision

Keep the new Hoolock kernel and its boot payload as the development baseline.
Do not change kernels again yet: the repository already pins the current tip of
Hoolock's `hoolock` branch, and no newer branch provides finished J81 peripheral
support. The useful newer work is isolated on Hoolock test branches and should
be ported selectively after the USB payload is tested on the iPad.

The implementation order is:

1. Test the Hoolock USB payload and recover a bidirectional debug channel.
2. Validate the already-wired buttons, RTC and backlight on that kernel.
3. Bring up Bluetooth on UART3, initially relying on bootloader power state.
4. Add the battery fuel gauge through a small HDQ serdev transport.
5. Clean up the old-SoC SPI controller support, then adapt touch.
6. Port the T7000 PCIe host path, then enumerate and enable BCM4350 Wi-Fi.

This order follows the dependencies actually present on J81. Wi-Fi is PCIe,
not SDIO. Touch depends on a missing old-Apple SPI controller variant. The
battery needs TI's HDQ-over-UART encoding, not Linux's generic 1-Wire UART
timings. Bluetooth is the first practical new peripheral because the kernel's
Broadcom HCI UART driver already supports the radio family.

## Evidence and limits

The repository's generated J81 DT is intentionally incomplete, so the hardware
map below also uses Apple's J82 ADT from SoMainline's collection. J82 is the
cellular sibling of J81 and uses the same T7001 platform, but it is supporting
evidence rather than authority for the Wi-Fi-only board. Before committing a
J81 peripheral node, dump the live J81 ADT through m1n1 and compare the relevant
node, GPIO descriptors, register ranges and calibration properties.

Apple's `function-*` properties use the OIPG record already decoded by m1n1:

```c
struct oipg {
    uint32_t phandle;
    char four_cc[4];
    uint32_t gpio;
    uint32_t flags;
};
```

That makes the AP GPIO numbers below evidence-backed. PMU GPIO register details
remain unknown because Hoolock has no D2207/Arabela PMIC GPIO provider.

Do not commit Apple firmware, radio NVRAM, touch calibration, or per-device
identifiers. Extract them locally from the device or a user-supplied IPSW and
inject them into test artifacts outside Git.

## Repository review

The overnight work added six commits on `main`, all already present on
`origin/main` before this review:

| Commit | Result |
| --- | --- |
| `e485856` | Round 8 proved asymmetric historical USB: host-to-iPad RX works, iPad-to-host TX stalls. |
| `10a27d0` | Researched the newer-kernel route and separated the historical diagnostic tag from development. |
| `0fe1811` | Pinned and built Hoolock Linux 7.3-rc1 at `6831bc7`. |
| `9896124` | Built `m1n1-hoolock-control`, including the Hoolock kernel, DT, initramfs overlay and ECM selection. |
| `f3363f4` | Fixed the Apple PMIC backlight build error and bundled RTC/backlight. |
| `b34f349` | Located the battery gauge and HDQ pin in the J82 ADT. |

The Hoolock kernel and the complete `m1n1-hoolock-control` payload build. Static
inspection confirms the framebuffer rename and configfs ECM override. They have
not been booted on the iPad. RTC and backlight are therefore **build-ready and
DT-wired**, not hardware-validated. The same distinction applies to GPIO keys.

The older 5.19 path remains useful as a diagnostic reference. It boots Linux,
shows a shell, creates `usb0` at `172.16.42.1`, receives 304 packets from the
Mac and resolves the Mac's real MAC address. Its bulk-IN endpoint queues a
transfer but never fills the physical FIFO, so it cannot reply. The Hoolock
payload changes the DWC2 implementation, PHY/reset sequence and gadget setup;
testing it is the smallest experiment that can either remove or preserve that
blocker.

## Driver matrix

| Subsystem | Hardware path | Current source/config | Concrete solution | Readiness |
| --- | --- | --- | --- | --- |
| USB gadget | T7001 USB PHY + DWC2 | Hoolock driver and ECM payload built | Boot the existing payload and test bidirectional traffic before editing it | Ready for hardware test |
| Buttons | AP GPIO 0/1/92/93 | DT nodes and `KEYBOARD_GPIO=y` | Verify all four input events | Ready for hardware test |
| RTC | D2207 PMIC child | Driver, DT and config built-in | Read/set/read time; confirm persistence behavior | Ready for hardware test |
| Backlight | D2207 PMIC child | Driver and DT built; compiler bug fixed | Exercise brightness range and blank/unblank | Ready for hardware test |
| Bluetooth | BCM4350-family radio on UART3 | `hci_bcm`, HCI UART BCM and serdev enabled | Add UART3/pinctrl/BT child; then solve PMU GPIO2 only if retained power is insufficient | Best first new peripheral |
| Battery | BQ27540-family gauge on UART5/HDQ | bq27xxx core exists; enabled generic W1-UART path is the wrong wire protocol | Add a minimal HDQ serdev frontend using Corellium's proven byte encoding and reuse bq27xxx core | Small driver required |
| Touch | `multi-touch,j82` on SPI3 | `apple_z2` exists but only for Mac Touch Bars; S5L SPI work is on test branches | Clean the old-controller SPI variant first, prove SPI3, then adapt Z2 firmware/calibration and protocol | Two-stage port |
| Wi-Fi | BCM4350 on T7000 PCIe port 1 through DART | brcmfmac PCIe source exists but CFG80211/BRCMFMAC are disabled; T7000 PCIe host is absent | Port T7000 PCIe host, add DART/port DT, enumerate endpoint, then enable brcmfmac and local firmware/NVRAM | Largest near-term driver task |
| Display | Bootloader framebuffer | simplefb works | Keep simplefb; native display/GPU is separate research | Usable baseline |
| Audio/GPU/NAND/cameras/Touch ID | Apple-specific blocks | No complete A8X stack | Defer until interactive tablet inputs/networking work | Out of current milestone |

### Kernel update assessment

The pinned commit is the current `hoolock` tip as of this review. Hoolock's own
A8/A8X feature page lists UART, GPIO, PMGR, I2C, USB2 device, RTC, framebuffer,
brightness and buttons; it does not claim Bluetooth, Wi-Fi or touch. A blind
move to another upstream release would lose Hoolock's T7001 work without adding
the missing board integrations.

Three Hoolock branches contain useful experiments:

- `tests/spi` (`0019398`) adds a simple S5L SPI variant.
- `tests/kat-spi` (`c065201`) has a more complete old-controller variant but
  also contains debug behavior and must be cleaned before use.
- `tests/bluetooth` (`6d756fb`) is for a T8015/BCM4349 device. It is useful for
  loader/property patterns, not as a J81 patch.

The current kernel already contains the old-Apple DART work. The remaining
PCIe host code is the limiting factor for Wi-Fi, not the kernel version.

## Exact peripheral map from the J82 ADT

| Device | Bus/resources | Signals |
| --- | --- | --- |
| Bluetooth | UART3 at `0x20a0cc000`, IRQ 161, 3,000,000 baud | TX GPIO14 alt2, RTS GPIO32 alt2, host wake GPIO164, power enable PMU GPIO2 |
| Battery gauge | UART5 at `0x20a0d4000`, IRQ 163, HDQ child | HDQ/battery SWI GPIO34 alt2 |
| Touch | SPI3 at `0x20a08c000`, IRQ 155, CS0 | CS GPIO51, IRQ GPIO84, display sync GPIO55, reset GPIO82, LDO GPIO95, analog power PMU resource `0x20e` |
| Wi-Fi control | UART2 at `0x20a0c8000`, IRQ 160 | TX GPIO136 alt2, RTS GPIO138 alt2, radio enable PMU GPIO3 |
| Wi-Fi data | PCIe port 1, max link speed 1 | wake GPIO165, CLKREQ GPIO174, PERST GPIO179; DART at `0x602002000`, IRQ 216 |

The ADT names the Wi-Fi endpoint `wlan-pcie,bcm4350`, which supersedes the
older teardown-based BCM4354/SDIO assumption in this repository.

## Phase 0: hardware gate with the existing Hoolock payload

Boot the already-built artifacts over the direct USB-C-to-iPad cable using the
same Pongo shell flow that produced the historical shell:

```sh
sudo /path/to/palera1n --pongo-shell \
  --override-pongo "$PWD/result-hoolock-control/Pongo.bin" --debug-logging
nix develop -c python3 boot/load_m1n1.py \
  result-hoolock-control/m1n1-linux.bin
```

After ECM enumerates on macOS, identify the new interface. Use DHCP if offered;
otherwise assign the host `172.16.42.2/16`. Test `ping 172.16.42.1` and the
existing telnet shell on port 23. Save the full Pongo log, screen output,
`ioreg` device tree, `ifconfig`, and packet counters in a dated session record.

Acceptance criteria:

- Linux reaches the existing visible shell or another unambiguous PID 1 marker.
- macOS enumerates the ECM function.
- At least one device-to-host packet arrives; ideally ping and telnet work in
  both directions.

If Linux stops earlier, compare the screen/log with the working historical
payload before changing drivers. If ECM has the same TX failure, instrument the
new DWC2 endpoint state and preserve the historical payload as the control.

## Phase 1: validate already-bundled devices

No new driver code is required.

1. Run `evtest` or inspect `/dev/input/event*` while pressing Home, Power and
   both volume buttons.
2. Read the RTC, set a known time, read it again, reboot without assuming that
   the write persists, and record the result.
3. Read the backlight maximum/current brightness, step through a conservative
   range, blank/unblank once, and restore the original value.

Acceptance is an observed input event or sysfs/RTC response on the physical
device. A successful kernel build is not a passing hardware test.

## Phase 2: Bluetooth on UART3

Add the smallest J81 DT patch:

- UART3 node with its register/IRQ/power-domain resources.
- TX GPIO14 and RTS GPIO32 pinctrl; enable RTS/CTS.
- a `brcm,bcm43540-bt` serdev child with 3,000,000 maximum speed.
- host-wake GPIO164 and a `bluetooth0` alias.

Start without `shutdown-gpios`. iBoot/m1n1 may leave the combo module powered,
which lets the UART/HCI path be proven without guessing D2207 PMIC registers.
m1n1 already copies `/chosen/mac-address-bluetooth0` to the aliased node. Extend
its ADT lookup from `/arm-io/bluetooth` to `/arm-io/uart3/bluetooth` only if the
live J81 ADT confirms that path and the kernel requires its calibration data.

If no HCI response occurs and the UART signals are correct, implement the
missing D2207 GPIO provider or a narrowly scoped radio-power child after the
PMU GPIO register offsets are derived from Apple behavior. Then describe PMU
GPIO2 as `shutdown-gpios`. Corellium's `gpio-hx-pmu-i2c.c` is a register-map
pattern, but its D2333 register offsets must not be copied onto D2207.

On the first successful probe, record the exact firmware filename requested by
`hci_bcm`, extract the matching `.hcd` from a local IPSW, and load it outside
Git.

Acceptance criteria:

- UART3 transmits and receives without overruns at the selected rate.
- `hci0` registers and reports a controller address.
- The locally supplied firmware loads and `bluetoothctl show` reports a powered
  controller.

## Phase 3: battery over HDQ/UART5

Do not use the currently enabled `w1-uart` master. It generates standard
1-Wire slots at 9600/115200 baud, while this board uses TI HDQ signaling through
the UART. Corellium's working transport uses 57,600 baud, no parity, two stop
bits, break/pulse signaling and encoded `0xfe`/`0xc0` bytes.

Implement one serdev transport that:

1. matches `ti,bq27545-hdquart` or a documented J81-specific compatible;
2. configures the UART and serializes one HDQ transaction at a time;
3. supplies register read/write callbacks to the existing upstream bq27xxx
   core rather than copying a second power-supply implementation;
4. times out cleanly and never loops forever when the gauge is absent.

Add UART5 and GPIO34 pinctrl to the board DT, then attach the gauge child. The
ADT says `bq27540`; upstream lacks that exact enum, so read the gauge
`DEVICE_TYPE` control response on hardware before selecting the closest
BQ27541/BQ27545 register layout.

Acceptance criteria:

- Repeated reads return a stable device type and plausible voltage,
  temperature, current and state of charge.
- Unplug/reboot and absent-device paths time out without blocking boot.
- Values agree approximately with iPadOS readings at the same charge state.

## Phase 4: SPI3, then touch

First port only the old-controller portions of Hoolock's `tests/kat-spi` work
into the pinned kernel. Remove its forced probe deferrals and debug logging,
retain the S5L8960X register layout and controller quirks, and add a binding or
compatible specific enough to avoid changing M-series behavior. Add SPI3 and
its PMGR domain to J81 DT and prove clocking, chip select and a bounded transfer
before binding a touch driver.

Then extend the Z2 touch path:

- add a J81/J82 compatible and SPI parameters, starting at 3 MHz;
- wire CS51, IRQ84, display-sync55, reset82 and LDO95;
- extend m1n1's multitouch ADT lookup to `/arm-io/spi3/multi-touch` and copy the
  live calibration blob to `apple,z2-cal-blob`;
- extract the matching Z2 firmware from a local IPSW and use the existing
  `apple_z2` firmware uploader/frame parser where the protocol matches;
- add the PMU analog-power sequence only if retained bootloader power is not
  sufficient, after the D2207 resource is understood.

Acceptance criteria:

- SPI3 produces stable, repeatable responses without IRQ storms.
- Firmware and calibration load from local files/data.
- Multitouch contacts track across the panel with correct orientation and no
  stuck contacts through suspend-free repeated tests.

## Phase 5: T7000 PCIe and BCM4350 Wi-Fi

The endpoint driver is not the first task. Upstream brcmfmac already maps
BCM4350 PCIe firmware names, but the current config does not enable CFG80211,
BRCMFMAC or BRCMFMAC_PCIE, and Linux has no J81 PCIe host description.

1. Dump and preserve the live J81 `apcie`, `dart-apcie0` and WLAN ADT nodes,
   including every T7000/A8X PHY and port tunable.
2. Add the DART node using Hoolock's existing `apple,s5l8960x-dart` support.
3. Port a T7000 variant into `pcie-apple.c` if its structure fits; otherwise
   use one small old-controller driver. Corellium's `pcie-hx.c` is a register
   and sequencing reference, but its H9P tunables are not valid for A8X.
4. Add only port 1, its ranges/MSI/DART relationship and wake/CLKREQ/PERST
   GPIOs. Prove config-space enumeration at 2.5 GT/s before enabling Wi-Fi.
5. Enable the wireless Kconfig closure and brcmfmac PCIe built-ins.
6. Extend m1n1's Wi-Fi ADT lookup to `/arm-io/uart2/wlan`, populate the
   `wifi0` alias, MAC address and board calibration properties.
7. Load `brcm/brcmfmac4350-pcie.bin` and the exact board NVRAM/calibration from
   local Apple firmware. Record any alternate name requested by the driver.

Acceptance criteria:

- The PCIe endpoint enumerates repeatedly after cold and warm boots.
- DART reports no unhandled faults under traffic.
- `wlan0` scans, associates and passes sustained bidirectional traffic without
  relying on USB networking.

## Change and test discipline

Keep each dependency independently revertible: USB baseline, BT DT, battery
transport, SPI controller, touch adaptation, PCIe host, and Wi-Fi integration.
Each patch should state the live ADT evidence it consumes and carry one focused
test. Build the complete `m1n1-hoolock-control` payload after every kernel or DT
change, then test on hardware before starting the next dependency.

Record each physical session in `docs/project-status.md` or a linked dated
note with:

- exact Git commit and artifact path;
- full boot command and cable topology;
- visible screen result and host enumeration;
- kernel log lines for the subsystem;
- acceptance result, failure signature and next single experiment.

## Primary sources

- [Hoolock Linux `hoolock` branch](https://github.com/HoolockLinux/linux/tree/hoolock)
- [Hoolock A8/A8X support matrix](https://github.com/HoolockLinux/docs/blob/master/features/A8.md)
- [Hoolock S5L SPI experiment](https://github.com/HoolockLinux/linux/commit/001939843409a0b27d5fd81a2d020d6779be2770)
- [Hoolock extended S5L SPI experiment](https://github.com/HoolockLinux/linux/commit/c065201fe71ed16efcb14569b5b40ef81343a70b)
- [SoMainline J82 ADT](https://github.com/SoMainline/adt_collection/blob/master/a8/J82.adt)
- [Linux brcmfmac PCIe driver](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)
- [Linux Broadcom HCI UART driver](https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_bcm.c)
- [Linux Apple PCIe host driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c)
- [Linux Apple Z2 touch driver](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/apple_z2.c)
- [Corellium HDQ-UART battery driver](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/bq27545-battery-hdquart.c)
- [Corellium old-Apple SPI controller](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/spi/spi-hx.c)
- [Corellium old-Apple touch driver](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/input/touchscreen/hx-touch.c)
- [Corellium old-Apple PCIe host](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/pci/controller/pcie-hx.c)
