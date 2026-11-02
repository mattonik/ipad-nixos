# Sibling Apple hardware: what each component can borrow (2026-11-02)

Question (Martin, 2026-11-02): which drivers and features from hardware
similar to the iPad Air 2 (iPhone 6 and friends) can J81 reuse, component
by component?

Labels: **E** checked in this session (command, source tree or API
response), **I** inference, **U** unknown. This survey builds on, and does
not repeat, `research/landscape.md`, `research/driver-gap.md`,
`research/j81-audio-sensors-source-survey.md`,
`research/j81-long-term-subsystems.md` and the Orchard audit
(`/mnt/project-files/research/orchard-reuse-audit.md`, 2026-10-29).

## 1. Answer at a glance

1. **No sibling Linux port is ahead of J81 on any component.** Hoolock's
   A7/A8/A8X device trees still describe only CPU, AIC, pinctrl, I2C, UART,
   watchdog, USB and the PMIC children (E, `hoolock` tip 2026-09-03). Our
   tree and Orchard's copy of it are the most advanced A8-family Linux code
   anywhere. The SoMainline feature matrix (A7–A11) is stale since 2022 and
   lists PCIe, touch, battery, charger and storage as unsupported (E).
2. **The useful sibling material is Apple's own, not Linux code.** Two
   sources are new and cheap:
   - **iPad mini 4 (J96/J97, A8/T7000)** ships in the *same* restore
     image as J81: `iPad_64bit_TouchID_15.8.8_19H422_Restore.ipsw`
     (E, ipsw.me API). The NAS copy already holds mini 4's DeviceTree and
     uses the same kernelcache family. It is the closest sibling with the
     same iPadOS 15.8.8 touch, SPI and PMGR code that unblocked touch.
   - **Apple TV HD (J42d, A8/T7000)** is still supported: tvOS
     **26.6.1 (23L781)** is its current signed build (E). It is the newest
     Apple-compiled T7000 code that exists, eleven years newer than iOS 8.1.
     It has no touch, battery or panel, but it does have PCIe Wi-Fi, UART
     Bluetooth, DART, PMGR, USB, and a DisplayPort→HDMI output path (I).
3. **Touch:** the best Linux reference remains Orchard's
   `feature/j71t-integration` (iPad 5, N1 controller C1F15,1, nearest to
   J81's C1F15,2) plus mainline `apple_z2`. For Apple behaviour, compare
   the J81 and J96 personalities in the 15.8.8 `AppleMultitouchSPI` and
   `AppleSamsungSPI` kexts; mini 4 uses the same BCM5976-generation
   controller (I, `research/hardware.md` lists iPad mini 1–4).
4. **Bluetooth:** Hoolock `tests/bluetooth` (2026-07-01) adds a
   `hci_bcm` path that uploads an ADT calibration blob in 0xe6-byte
   chunks for BCM4349B1 (E). It is aimed at later devices, but it is the
   only public Linux code that does Apple-style UART BT calibration upload.
   Read it before the next J81 BT attempt.
5. **Display:** mainline `drivers/gpu/drm/adp` ("Apple pre-DCP display
   pipe", binding `apple,h7-display-pipe`, Sasha Finkelstein) drives the M1
   touch bar (E). "H7" is the A8 generation's internal codename (I). Whether
   J81's `disp0` is the same IP is **U** and cheap to check: compare J81's
   `disp0` ADT node and its iOS 15 kext class with the t8103 touch bar pipe.
6. **GPU:** the upstream `drm/imagination` driver now probes a Series 6XT
   core (GX6250 in MediaTek MT8173), with Vulkan reported via Zink in the
   v4 series (E, LKML 2026-07). A8/A8X GPUs are Series 6XT too (I), but
   Apple's GPU firmware and BVNC are not IMG's. Track it; nothing to port.

## 2. The sibling family

| Device | Board | SoC | Latest Apple OS | IPSW (E, ipsw.me) | Closeness to J81 |
|---|---|---|---|---|---|
| iPad Air 2 | J81/J82 | T7001 (A8X) | iPadOS 15.8.8 | iPad_64bit_TouchID_15.8.8_19H422 | target |
| iPad mini 4 | J96/J97 | T7000 (A8) | iPadOS 15.8.8 | **same file** | same OS build, same touch family, same PMIC family (I) |
| Apple TV HD | J42d | T7000 | tvOS 26.6.1 | AppleTV5,3_26.6.1_23L781 | newest T7000 kexts; no touch/battery |
| iPhone 6 / 6 Plus | N61/N56 | T7000 | iOS 12.5.8 | iPhone_4.7_12.5.8_16H88 | touch, Tristar, baseband; older code |
| iPod touch 6 | N102 | T7000 | iOS 12.5.8 | iPodtouch_12.5.8_16H88 | like N61 without baseband |
| iPad Air 1, mini 2/3 | J71–J73, J85–J87 | S5L8960X (A7) | iOS 12.5.8 | iPad_64bit_12.5.8_16H88 | previous generation; Hoolock `ans1` storage targets these too |
| iPad 5 | J71s/J71t | A9 | iPadOS 16.7.x | – | Orchard N1 touch work (C1F15,1) |

Upstream Linux already has device trees for every T7000 board above
(`t7000-n61.dts`, `-n56`, `-n102`, `-j42d`, `-j96`, `-j97`) and all A7
boards (E, Hoolock tree). They contain no peripheral nodes J81 lacks.

## 3. Component by component

| Component | J81 state (2026-11-02) | Best sibling source | What to take | Effort |
|---|---|---|---|---|
| Touch (BCM5976 / Z2-N1, SPI3) | First firmware ACK after matching 15.8.8 SPI start order | Orchard `feature/j71t-integration` `input/0005-0008`, `spi/0003-0004`; mainline `apple_z2`; J96 personality in 15.8.8 `AppleMultitouchSPI` | Calibration/execute sequence and gen-1 framing; diff the J81 and J96 Info.plist personalities | M–L |
| SPI controller (S5L) | Ported from Hoolock `tests/kat-spi` + 15.8.8 start-order fix | 15.8.8 `AppleSamsungSPI` (shared with J96); Orchard `spi/0001` (GPIO CS delays applied twice) | Already on our path; adopt `spi/0001` | S |
| Display | simplefb only | mainline `drm/adp` (`apple,h7-display-pipe`); tvOS 26 DisplayPort kexts on J42d | First check whether J81 `disp0` matches the ADP register layout | U, then M–L |
| GPU (GXA6850) | none | upstream `drm/imagination` Series 6XT (GX6250) | Nothing yet; Apple firmware differs | – |
| Wi-Fi (BCM4350, PCIe) | Working (H1B) | tvOS 26.6.1 J42d PCIe/DART/brcm kexts (I: Wi-Fi chip **U**, check J42d ADT) | Cross-check the PCIe power/MSI sequence against 2026 Apple code | S to read |
| Bluetooth (UART3) | `hci0` registers; chip silent; GPIO2/0x0403 path under study | Hoolock `tests/bluetooth` calibration upload; J42d/J96 ADT `bluetooth` nodes and `AppleBluetooth*` kexts | Compare power-sequence properties across J81/J96/J42d ADTs | S–M |
| Battery gauge (BQ27545, HDQ) | Working live | iPhone 6 / mini 4 use the same HDQ-over-UART pattern (I) | Nothing to take; ours is ahead | – |
| Charger (D2207 + Tristar) | Policy via `0x04c0`; event block unknown | Orchard `apple_tristar_charger` (D2365); N61/J96 share Tristar (`research/hardware.md`) | Tristar register map, if Orchard's driver documents it | L |
| PMIC (D2207) | RTC, backlight, GPIO provider | J96 ADT `pmu` node; Sandcastle `gpio-hx-pmu-i2c.c`, `regulator/hx-pmu-i2c-pwrsw.c` | Power-switch (`pwrsw`) model as a template for BT/LPO rails | S to read |
| USB | Working gadget | Orchard `usb/0001-0002` (dwc2 resume, f_ecm resend) | Adopt | S |
| Storage (ANS1/ASP) | Read-only verified | Hoolock `ans1` branch (A7/A8) | Already used | – |
| Audio (CS42L81, MAX98721) | none | J96 shares the codec family (I); Asahi `apple-mca` | Confirm J96 vs J81 codec nodes; no Linux driver exists | L |
| Sensors (M8/Oscar, ALS) | none | N61/J96 ADT `oscar` nodes | Protocol still unknown | L |
| Cameras, Touch ID, baseband | none | – | Out of scope | – |

## 4. Recommended next steps (cheapest first)

1. **Extract J96/J97 DeviceTrees from the IPSW already on the NAS** and
   diff them against J81 for `multi-touch`, `spi3`, `bluetooth`, `pmu`,
   `disp0`, `audio`. No download needed.
2. **Pull only the J42d tvOS 26.6.1 kernelcache** (remote extraction with
   `ipsw download ipsw --device AppleTV5,3 --build 23L781 --kernel`, as
   done for iOS 8.1) and list its T7000 kexts. Use it to cross-check
   PCIe/DART/BT power code against a 2026 Apple build.
3. **Read Hoolock `tests/bluetooth`'s calibration upload** before the next
   BT hardware run.
4. **Check `disp0` against `drm/adp`**: one ADT comparison decides whether
   native display has a mainline starting point.
5. Adopt Orchard `spi/0001` and `usb/0001-0002` (already recommended by
   the 2026-10-29 audit).

For the parallel firmware-library work, the useful downloads are, in order:
the J42d tvOS 26.6.1 kernelcache and DeviceTree, the N61 iOS 12.5.8
kernelcache and DeviceTree, and the iPad Air 1 iOS 12.5.8 image for A7
comparison. J96/J97 need nothing new.

## 5. Sources

- HoolockLinux/linux branches (`git ls-remote`, shallow fetch, 2026-11-02):
  `hoolock` 2026-09-03, `tests/bluetooth` 2026-07-01, `tests/kat-spi`
  2026-02-14, `ans1` 2026-09-04, `tests/adp` 2025-10-08.
- corellium/linux-sandcastle `sandcastle-5.4`: `drivers/*/hx-*`
  (A10; PMU GPIO, power switch, SPI, touch, PCIe).
- SoMainline/linux-apple-resources README (feature matrix, 2022).
- ipsw.me API v4 for iPad5,3, iPad5,1, iPhone7,2, iPod7,1, AppleTV5,3,
  iPad4,1 (2026-11-02).
- [drm: adp: Add Apple Display Pipe driver](https://patchew.org/linux/20250114-adpdrm-v4-0-e9b5260a39f1@gmail.com/20250114-adpdrm-v4-2-e9b5260a39f1@gmail.com)
- [apple,h7-display-pipe binding](https://mjmwired.net/kernel/Documentation/devicetree/bindings/display/apple,h7-display-pipe.yaml)
- [powervr: MT8173 GPU support v4](https://lkml.iu.edu/2607.3/12558.html),
  [Phoronix on GX6250](https://www.phoronix.com/news/PowerVR-GX6250-MT8173)
- [SoMainline feature matrix](https://github.com/SoMainline/linux-apple-resources)
- [Apple TV HD teardown listing](https://techinfodepot.shoutwiki.com/wiki/Apple_TV_A1625_(4th_generation))
