# Feasibility assessment: Linux/NixOS on iPad Air 2

Updated 2026-09-08. This supersedes the February 2026 forecast with results
from the physical J81 and the current source/ADT review.

## Verdict

A tethered, framebuffer-based Linux tablet is feasible. The iPad Air 2 already
boots Linux to a visible interactive shell. The immediate usability blocker is
a bidirectional control channel: the historical USB gadget receives traffic
from macOS but its device-to-host endpoint stalls. A newer Hoolock USB payload
is built and is the next hardware test.

A practical standalone system still needs substantial peripheral work.
Bluetooth and battery have short, evidence-backed paths. Touch needs the old
T7001 SPI controller before the existing Z2 protocol code can be adapted.
Wi-Fi uses BCM4350 over T7000 PCIe, so it requires a host-controller port before
brcmfmac can help. Native display/GPU, audio and internal storage remain
long-term work.

The full implementation plan is
[docs/plans/2026-09-08-ipad-air2-driver-bringup.md](../docs/plans/2026-09-08-ipad-air2-driver-bringup.md).

## Milestones

### Boot and visible console — achieved

The checkm8 → PongoOS `bootm` → m1n1 path boots the historical Linux kernel,
all A8X cores and a postmarketOS initramfs to a visible `/ #` shell. The
bootloader-initialized framebuffer is sufficient for software-rendered output.

### USB control channel — partial

CDC-ECM enumerates natively on macOS. The iPad's `usb0` receives packets,
updates RX counters and learns the Mac's ARP entry. Its bulk-IN endpoint fails
to place a queued reply in the physical FIFO. Hoolock's newer DWC2/PHY path and
ECM payload build successfully but have not been booted on the iPad.

### Buttons, RTC and backlight — build-ready

The GPIO keys and Apple PMIC RTC/backlight nodes and drivers are present in the
Hoolock artifact. A compiler error in the backlight driver was fixed. These
features are not counted as working until tested on hardware.

### Bluetooth — achievable with targeted DT/power work

The T7001-family ADT maps the combo radio to UART3 at 3 Mbaud. Hoolock already
enables Broadcom HCI UART support. Add the UART and serdev DT nodes first and
test the power state inherited from iBoot. If the module is off, derive D2207
PMIC GPIO2 control; Hoolock currently has no PMIC GPIO provider. Firmware must
be extracted locally and kept outside Git.

### Battery — achievable with a small transport driver

The ADT identifies a BQ27540-family gauge on UART5/HDQ GPIO34. Linux's enabled
generic W1-UART path uses the wrong signaling. Corellium published a working TI
HDQ-over-UART algorithm. A minimal serdev frontend can reuse the upstream
bq27xxx core, avoiding a second power-supply driver.

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

### Native GPU, audio and internal storage — deferred

No complete A8X PowerVR platform stack, native display pipeline, audio stack or
Apple NAND/FTL stack is available. The usable milestone should use simplefb,
software rendering, USB or network storage, and external audio if needed.

## Dependency path

```text
working boot
    └─ Hoolock USB test ─ bidirectional debug channel
           ├─ validate buttons / RTC / backlight
           ├─ UART3 ─ Bluetooth ─ optional D2207 GPIO power
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
| New Hoolock payload does not boot | No newer USB result | Preserve and compare with the known historical control artifact |
| J82 wiring differs from J81 | Wrong GPIO/resource assignment | Dump live J81 ADT before committing each board node |
| D2207 PMIC GPIO registers remain unknown | Bluetooth/touch cold-power failure | Test retained bootloader power first; derive registers before driving them |
| Wrong radio/touch firmware | Probe or calibration failure | Use exact local IPSW/device artifacts and record requested filenames; do not commit blobs |
| PCIe PHY tunables copied from another SoC | Link failure or unstable hardware | Use A8X ADT values, start with port 1 at 2.5 GT/s, and test DART faults |
| USB remains asymmetric | Slow hardware iteration | Add focused Hoolock DWC2 endpoint diagnostics before unrelated driver changes |

## Recommended development order

1. Boot the existing Hoolock payload over the direct cable and record ECM
   enumeration, ping/telnet, screen and logs.
2. Test buttons, RTC and backlight without changing the kernel.
3. Add Bluetooth UART3 DT and local firmware; add PMIC power only if required.
4. Implement and test the battery HDQ serdev frontend on UART5/GPIO34.
5. Port and prove S5L8960X SPI3, then adapt touch.
6. Port T7000 PCIe/DART, enumerate BCM4350, then enable brcmfmac.
7. Build the minimal NixOS userspace after the input/network hardware has a
   stable interface.

## Practical target

The credible medium-term system is RAM- or network-rooted Linux with simplefb,
software rendering, USB debug access, Bluetooth input, battery reporting,
touch, and eventually Wi-Fi. Native GPU acceleration, internal NAND boot,
cameras, Touch ID and polished suspend are separate research projects.
