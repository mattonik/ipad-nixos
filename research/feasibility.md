# Feasibility assessment: Linux/NixOS on iPad Air 2

Updated 2026-09-10. This supersedes the February 2026 forecast with results
from the physical J81 and the current source/ADT review.

## Verdict

A tethered, framebuffer-based Linux tablet is feasible. The iPad Air 2 boots
Linux to a visible shell and the Hoolock payload provides working bidirectional
USB networking and remote access at `172.16.42.1:23`.

A practical standalone system still needs substantial peripheral work.
Bluetooth and battery have short, evidence-backed paths. Touch needs the old
T7001 SPI controller before the existing Z2 protocol code can be adapted.
Wi-Fi uses BCM4350 over T7000 PCIe, so it requires a host-controller port before
brcmfmac can help. Native display/GPU and audio remain long-term work. Internal
storage now has a concrete Hoolock ANS1 WIP branch and is the closest of those
previously deferred subsystems, but its first local build must be forced
read-only. See the
[long-term subsystem plan](j81-long-term-subsystems.md).

The full implementation plan is
[docs/plans/2026-09-08-ipad-air2-driver-bringup.md](../docs/plans/2026-09-08-ipad-air2-driver-bringup.md).

## Milestones

### Boot and visible console — achieved

The checkm8 → PongoOS `bootm` → m1n1 path boots the historical Linux kernel,
all A8X cores and a postmarketOS initramfs to a visible `/ #` shell. The
bootloader-initialized framebuffer is sufficient for software-rendered output.

### USB control channel — achieved

The Hoolock DWC2/PHY path enumerates as CDC-ECM and carries bidirectional
traffic. Ping and the telnet shell work over the direct cable.

### Buttons pending; RTC and backlight achieved

RTC and backlight are hardware-verified. The GPIO keys remain untested.

### Bluetooth — UART proven, power control remains

UART3 and manual `hci0` registration are hardware-confirmed. The chip stays
silent because D2207 PMU GPIO2 power control is missing. Implement and measure
that provider before adding the standard `hci_bcm` serdev child. Firmware must
be extracted locally and kept outside Git.

### Battery — working live; permanent-DT reboot remains

The HDQ-UART frontend identifies a BQ27545 and exposes stable bq27xxx readings
on the live J81 after correcting GPIO34 to peripheral function 1. Ten driver
rebinds returned the same device ID without errors. The rebuilt DT must still
be booted and reproduced across warm and cold boots.

### Touch — feasible, requires two stages

The touch controller is on SPI3 with known AP GPIOs. Hoolock's test branches
contain unfinished S5L8960X SPI support, while current `apple_z2` contains a
firmware uploader and frame parser for related Mac Touch Bars. First clean and
prove the SPI controller. Then add the J81 binding, live-ADT calibration,
locally extracted firmware and verified PMIC power sequence.

### Wi-Fi — feasible but high effort

The ADT identifies BCM4350 on T7000 PCIe port 1, not BCM4354 on SDIO. Upstream
brcmfmac supports BCM4350 PCIe firmware, but J81 lacks the PCIe host and port
description. Hoolock already carries the old-Apple DART variant. Port the
T7000 PCIe host using live A8X tunables, prove endpoint enumeration, then enable
CFG80211/BRCMFMAC/BRCMFMAC_PCIE and provide local firmware/NVRAM.

### Native GPU and audio deferred; internal storage now WIP

No complete A8X PowerVR platform stack, native display pipeline or audio stack
is available. Hoolock's experimental ANS1 Linux and m1n1 branches now provide a
specific internal-storage path, including the T7001 mailbox/RTKit support, ASP
block driver and iBoot-loaded firmware handoff. The driver is unsafe to test
unchanged because it enables user-area writes and lacks recovery; the first
payload must remove write unlock and expose every namespace read-only. Until
that gate passes, the usable milestone should continue to use simplefb,
software rendering, and RAM, USB or network storage.

## Dependency path

```text
working boot
    └─ Hoolock USB test ─ bidirectional debug channel
           ├─ validate buttons / RTC / backlight
           ├─ UART3 ─ Bluetooth ─ D2207 GPIO power
           ├─ UART5 HDQ ─ battery gauge
           ├─ S5L8960X SPI3 ─ Z2 touch
           └─ DART + T7000 PCIe ─ BCM4350 Wi-Fi
```

Wi-Fi no longer sits on the shortest path to useful hardware feedback.
Bluetooth is the first new peripheral because its bus driver and HCI support
already exist. USB remains first because every later driver benefits from a
reliable log and shell.

## Main risks and controls

| Risk | Effect | Control |
| --- | --- | --- |
| New peripheral patch breaks boot | Slow hardware iteration | Keep each bus/DT change separately revertible and compare with the working Hoolock payload |
| Private ADT data leaks | Device identifiers or calibration enter Git | Commit only sanitized resources; keep the captured J81 ADT ignored |
| D2207 PMIC GPIO registers remain unknown | Bluetooth/touch cold-power failure | Test retained bootloader power first; derive registers before driving them |
| Wrong radio/touch firmware | Probe or calibration failure | Use exact local IPSW/device artifacts and record requested filenames; do not commit blobs |
| PCIe PHY tunables copied from another SoC | Link failure or unstable hardware | Use A8X ADT values, start with port 1 at 2.5 GT/s, and test DART faults |
| USB remains asymmetric | Slow hardware iteration | Add focused Hoolock DWC2 endpoint diagnostics before unrelated driver changes |

## Recommended development order

1. Boot and reproduce the hardware-proven GPIO34 function-1 battery fix.
2. Port and prove S5L8960X SPI3, then adapt touch.
3. Finish Bluetooth's measured D2207 PMU GPIO2 power path.
4. Port T7000 PCIe/DART, enumerate BCM4350, then enable brcmfmac.
5. Build the minimal NixOS userspace after the input/network hardware has a
   stable interface.

Keep native display/GPU work deferred; simplefb and software rendering cover
the current tablet milestone.

## Practical target

The credible medium-term system is RAM- or network-rooted Linux with simplefb,
software rendering, USB debug access, Bluetooth input, battery reporting,
touch, and eventually Wi-Fi. Native GPU acceleration, internal NAND boot,
cameras, Touch ID and polished suspend are separate research projects.
