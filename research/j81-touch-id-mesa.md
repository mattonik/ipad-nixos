# J81 Touch ID (Mesa), the SEP, and what the T1 Linux work does and does not transfer

Date: 2026-09-10

Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001

## Why this was researched

A 2026-09-10 post by Nico Nistal ([@niconistal](https://x.com/niconistal/status/2097906524559384816))
reported Touch ID working under Linux on a Touch Bar MacBook Pro whose Apple
firmware data had been wiped -- getting the T1 coprocessor to "regenerate its
own data from Linux" instead of the documented "reinstall macOS" recovery,
after which [@0xBOYD](https://github.com/standardagents/t1bridge)'s `t1bridge`
handled the fingerprint. The question raised for this project: can that work,
or its approach, be leveraged for the iPad Air 2?

Short answer: **the code does not transfer, and Touch ID on J81 is not a
near-term target -- but the investigation produced real, useful J81 hardware
evidence that shortens two items already on this project's roadmap.**

## What t1bridge actually is

[`standardagents/t1bridge`](https://github.com/standardagents/t1bridge)
(Rust, created 2026-09-05) is Linux support for Apple's T1 "iBridge" in
2016-2017 Touch Bar MacBook Pros. It covers the Touch Bar display, camera
(through UVC), ambient-light sensor, xART storage, keybag, and Touch ID
exposed through standard `fprintd`/`pam_fprintd`.

Two facts from its own README matter most here:

- Touch ID requires that Mac's original `EFI/APPLE/EMBEDDEDOS/FDRData`.
  Machine-specific; another Mac's backup cannot substitute. The documented
  recovery for lost data is to reinstall macOS and let it complete first boot
  so the data regenerates. **That is exactly the step the post claims to have
  bypassed from Linux** -- and the t1bridge author's public reply asks for a
  PR, so as of this writing the technique is not in the repository.
- "General Secure Enclave key services: 🔴 Not implemented. No
  general-purpose signing/key-management API; Touch ID support does not imply
  these services exist."

That second line is the important one for calibrating expectations: even with
Apple's own coprocessor firmware still running and a working host bridge, that
project has not obtained general SEP services.

## The architectural difference

| | T1 MacBook Pro | iPad Air 2 (J81) |
| --- | --- | --- |
| CPU running Linux | Intel x86_64 host | the Apple A8X application processor itself |
| Apple coprocessor | T1: a separate SoC running Apple's own EmbeddedOS, still alive and serving the host | SEP: on-die in the A8X, also still alive (see below) |
| Host to coprocessor link | USB service interfaces (NCM network, UVC, HID) that Apple's firmware exposes | an IOP mailbox (`iop-nub,sep`), no Apple-provided service interface for a foreign OS |
| Touch ID sensor attaches to | the T1; the host never talks to the sensor directly | **an ordinary AP-side SPI bus** (see below) |
| Machine-specific provisioning data | `EFI/APPLE/EMBEDDEDOS/FDRData` on the ESP -- a hard blocker once lost | supplied fresh by iBoot in the ADT on every boot, plus an on-device `mesa-eeprom` node |

t1bridge is a *client* of Apple firmware that is still running on hardware
Linux does not own. Nothing in it reimplements Apple's biometric crypto, and
nothing in it is portable to an A-series device, where Linux has displaced
iOS on the very processor that would be the client.

## What the real J81 ADT shows

All of the following is read from this project's own private J81 capture
(`artifacts/adt/`, git-ignored). Board-level facts only; no per-device data.

### Touch ID sensor: `biosensor,mesa`, on SPI2

| Resource | Real J81 value |
| --- | --- |
| Compatible / device_type | `biosensor,mesa` / `mesa` |
| Parent bus | **SPI2** (`spi-1,samsung`, the same Apple S5L SPI controller family as SPI3) |
| Interrupt | `0x79` = 121, type 3, via GPIO interrupt-parent `0x1f` |
| SPI frequency | `0x007a1200` = 8 MHz |
| Power | `function-mesa_pwr`, PMU phandle `0x4e`, **`Lump`** format, arg `0x304` |
| Power (proto variant) | `function-mesa_pwr_preprotorev3`, same `Lump` format, arg `0x307` |
| Event path | `function-hid_event_dispatch` -> phandle `0x85`, which is the `buttons` node (Touch ID lives in the home button) |
| Sibling node | `mesa-eeprom` -- presumed per-device pairing/calibration storage; **not read, not to be committed** |

`reg` is a packed multi-word property of the same shape as the `multi-touch`
child's, and is likewise not yet decoded.

### SEP: alive, with xART, under our own boot chain

| Resource | Real J81 value |
| --- | --- |
| Compatible / role | `iop,s5l8960x` / `SEP` |
| Register base | `0x0da00000`, size `0x2000` |
| Interrupts | 98, 97, 100, 99 (mailbox in/out pairs) |
| Clock/power gates | `0x7d` |
| Anti-replay | `has-art` present; a `.sep.art=0` boot argument also appears in the capture |
| **Firmware state** | **`sepfw-loaded = 0x00000001`** |
| Mailbox child | `iop-nub,sep` |

`sepfw-loaded = 1` is worth recording: in this project's own
checkm8 -> PongoOS boot, iBoot has already loaded and started SEP firmware
before we take the AP. The SEP is running while our Linux runs. checkm8 is an
AP bootrom exploit and is not a SEP break, so "running" here means "present
and outside our control", not "available to us".

## Verdict for this project

**Touch ID on J81 is not a near-term target.** Fingerprint matching happens
inside the SEP and the sensor is cryptographically paired to it -- the same
reason a replaced home button loses Touch ID on iOS. Reaching it would need
an implementation of Apple's AP-to-SEP mailbox protocol *and* its biometric
session/pairing protocol, on a security domain checkm8 does not open. The T1
project, in a materially easier position, still reports no general SEP
services. Nothing about the post changes that.

**Two things from this investigation do help work already planned:**

1. **The SPI controller port is shared infrastructure.** Touch ID is on SPI2
   and the touchscreen on SPI3, both `spi-1,samsung` -- the same controller
   family `kernel/patches/0007-spi-apple-add-s5l8960x-support.patch` ports.
   Whatever proves that driver on SPI3 also covers SPI2.
2. **The already-resolved `Lump` decode reads straight across.** The touch
   plan's 2026-09-10 result established that a `Lump` argument encodes a
   zero-based D2207 LDO index in its low byte and flags in the next
   (`0x20e` = LDO 14, flags `0x02`, enable-only). Applying that to every
   `Lump` consumer in the ADT gives the PMU rail for each subsystem at no
   extra research cost -- see the table below.

**One transferable pattern, not code.** t1bridge's shape -- speak the Apple
protocol to firmware that is still running, and expose the result through
*standard* Linux interfaces (`fprintd`, UVC, HID) rather than inventing new
ones -- is the model this project already follows with mainline `apple_z2`,
`bq27xxx`, and simpledrm. Its prominent "back up the machine-specific data
before you erase anything" warning is also a useful mirror of this project's
own rule about `multi-touch-calibration`, `mesa-eeprom`, and the raw ADT:
never commit per-device data.

Worth noting an asymmetry in our favour: the T1 project's hardest problem is
machine-specific data that is destroyed once the ESP is wiped. This project
does not have that problem for touch -- iBoot hands us a fresh ADT, with
calibration in it, on every single boot.

## Side result: every `Lump` power rail on J81, decoded

Nine ADT properties use the `Lump` format. Applying the touch plan's resolved
decode (low byte = zero-based D2207 LDO index, next byte = flags) to all of
them:

| Consumer | Node | Raw arg | LDO index | Flags |
| --- | --- | ---: | ---: | ---: |
| `function-power_ana` | `multi-touch` (SPI3) | `0x20e` | 14 | `0x02` |
| `function-mesa_pwr` | `mesa` Touch ID (SPI2) | `0x304` | 4 | `0x03` |
| `function-mesa_pwr_preprotorev3` | `mesa`, proto variant | `0x307` | 7 | `0x03` |
| `function-oscar_power1` | `oscar` motion hub | `0x213` | 19 | `0x02` |
| `function-oscar_power2` | `oscar` motion hub | `0x215` | 21 | `0x02` |
| `function-sensor_power` | `oscar` motion hub | `0x202` | 2 | `0x02` |
| `function-acc_pwr` | `dock` (Lightning accessory) | `0x5` | 5 | `0x00` |
| `function-acc_sw_en` | `dock` | `0x80000005` | 5 | `0x00` + top bit `0x80000000` |
| `function-acc_sleep_pwr` | `dock` | `0x216` | 22 | `0x02` |

Only flags `0x02` (enable-only, preserve programmed voltage) is established
from Apple's own driver text. Flags `0x03`, `0x00`, and the `0x80000000` top
bit on `acc_sw_en` are **not** decoded -- do not assume they are also
enable-only. The LDO index decode is the reliable part here; each rail's
voltage register and enable bit still need the same per-LDO descriptor
lookup that LDO14 got.

## Side result: the motion sensors are behind a firmware-loaded coprocessor

The `oscar` node is Apple's CoreMotion sensor hub, and this materially
corrects an assumption in [`research/hardware.md`](hardware.md), whose device
table lists the accelerometer as "Bosch BMA280 / bma180 (IIO) / Driver
exists; needs DT" and the gyroscope as "Needs chip ID + DT".

| Resource | Real J81 value |
| --- | --- |
| Compatible / device_type | `apple-oscar`, `oscar1`, `oscar` / `oscar` |
| Version | `oscar-version = 0x00020000` |
| **Firmware** | **`firmware-image = coremotion-oscar2-ipad5b.image`** |
| Power | three `Lump` rails: LDO 19, LDO 21, and LDO 2 (`sensor_power`) |
| Reset | `function-reset`, OIPG format, PMU phandle `0x4e` |
| Time sync | `function-time-sync`, OIPG, AP GPIO `0x34` = 52, alt-function 1 |
| Child | HID node with `device-usage-page = 0xff00` and gyro calibration data (per-device; not read, not to be committed) |

The practical consequence: motion sensors on J81 are **not** a "point a
generic IIO driver at an I2C chip and add a DT node" job. The individual MEMS
parts sit behind an Apple coprocessor that needs its own firmware image
(`coremotion-oscar2-ipad5b.image`, extracted from an IPSW and kept out of
Git, exactly like the Wi-Fi/Bluetooth and Z2 touch firmware), plus a reset
line, a time-sync pin and three PMU rails, and it reports through HID usage
pages rather than raw sensor registers. That places motion sensors in the
same firmware-dependent class as Wi-Fi/BT, not in the easy class the current
hardware table implies.

## Already-known items this corroborates

The SEP is one of four IOP coprocessors in the ADT (`role` values: `AP`,
`SEP`, `ANS`, `SIO`). The ANS one -- internal NAND storage, whose nub is
`iop-nub,rtbuddy` -- is already researched in depth in
[`research/j81-long-term-subsystems.md`](j81-long-term-subsystems.md), which
ranks it the closest of the long-term items and already tracks Hoolock's
ANS1 branches, m1n1's `ans1` branch, and Corellium's prior art. Nothing here
changes that plan; it only confirms at ADT level that ANS uses the same
RTKit/rtbuddy mailbox family the existing plan assumes. `SIO` is the
DMA/serial-IO coprocessor referenced by the `dma-parent` properties on the
UART and SPI nodes.

## Addendum, 2026-09-12: the "Omarchy M" Touch ID claim, and why it's architecturally *closer* to J81 than t1bridge

A 2026-09 [omarchy.org announcement](https://omarchy.org/news/2026/09/introducing-omarchy-m/)
claims a contributor named Dj "got Touch ID working by talking directly to the
Secure Enclave" on Apple Silicon Macs, alongside GPU driver work, an
independent reverse-engineering of Apple's M5-era "N1" wireless chip
(Miguel Cruz), and other M-series bring-up. Worth a real look, because unlike
the T1 case above, **this one does not fail on architecture alone**:

| | T1 MacBook Pro | Apple Silicon Mac (M1-M5) | iPad Air 2 (J81) |
| --- | --- | --- | --- |
| SEP location | separate T1 SoC, its own EmbeddedOS | **on-die in the M-series SoC** | **on-die in the A8X SoC** |
| Host-to-SEP link | USB service interfaces | **on-die IOP mailbox** | **on-die IOP mailbox (`iop-nub,sep`)** |
| CPU running Linux | separate x86 host | the AP itself, same as SEP's die | the AP itself, same as SEP's die |

An M-series Mac's SEP is the *same architectural family* as J81's -- on-die,
IOP-mailbox-based, with Linux running on the very AP that would be the
mailbox's other end. If Dj's claim is real and general (not just "unlocked
this one already-provisioned key"), it is a genuinely different, more
relevant data point than t1bridge, and the reasoning above ("Linux has
displaced iOS on the client processor, no vendor-provided service interface")
would need re-examination rather than automatic dismissal.

**But the claim does not hold up to the same scrutiny t1bridge got.** Checked
before writing anything further:

- **No repository, commit, or technical writeup exists for this specific
  claim.** Contrast with the same announcement's USB-C display work, credited
  to Jaidip Subedi with a linked repo
  (`github.com/subedijaidip/dp-altmode-t8112`) that can be read directly.
  Every search result for the SEP/Touch-ID claim traces back to the same
  single marketing sentence, restated.
- **Asahi Linux's own progress reports don't mention it.** Asahi Linux is the
  established, technically rigorous project for exactly this hardware class,
  publishes detailed progress reports on a roughly bimonthly cadence, and a
  SEP break would be major news there. Checked the most recent one available
  ([Progress Report: Linux 7.2](https://asahilinux.org/2026/08/progress-report-7-2/),
  2026-08) directly: no mention of Touch ID, SEP, or Omarchy.
- **The GPU-driver claim itself looks like relabeled existing work.** A
  companion Omarchy repository, `omarchy-mx-mac`, describes its own graphics
  support as "hardware-accelerated Apple GPU graphics through **the Mesa
  vulkan-asahi driver**" -- Asahi Linux's own existing, upstream AGX driver.
  That is at minimum an announcement leaning on a well-established project's
  output while presenting it as new work by named individuals, which is
  reason to read the rest of the same announcement (including the SEP claim)
  as promotional copy rather than as a verified engineering report.

**Conclusion: no change to the verdict above, for a reinforced reason.**
Touch ID on J81 remains not a near-term target -- checkm8 is a bootrom
exploit, not a SEP break, and that has not changed. But the additional reason
is now: even the trigger for reconsidering it does not currently survive
verification. Worth revisiting *if* real evidence (a repo, a technical
writeup, or Asahi's own progress reports) ever substantiates the M-series
claim specifically -- at which point the architectural closeness above would
make it worth reading in real detail, not dismissing on the T1 template.

## What to watch

Two narrow items, both tracked in `research/watchers.md`:

1. Whether the "regenerate the coprocessor's own provisioning data from
   Linux" technique lands in t1bridge as a real, described mechanism (see
   above).
2. Whether Asahi Linux's own progress reports -- the high-signal source, not
   the omarchy.org announcement -- ever report real SEP/Touch-ID progress on
   M-series. Added 2026-09-12 after the Omarchy M claim above failed to
   independently verify; per the architecture table in that addendum, a
   *real* M-series result would be worth reading in detail specifically
   because it is architecturally closer to J81 than t1bridge was.

## Sources

- [The post that prompted this](https://x.com/niconistal/status/2097906524559384816)
- [standardagents/t1bridge](https://github.com/standardagents/t1bridge)
- Private J81 ADT capture under ignored `artifacts/adt/` (board facts only, reproduced above)
- [J81 touch/SPI3 plan](../docs/plans/2026-09-09-j81-touch-spi3.md), which owns the `Lump` decoding work
- [Introducing Omarchy M](https://omarchy.org/news/2026/09/introducing-omarchy-m/) -- the 2026-09-12 addendum's trigger; treat its driver claims as promotional copy, not verified reports (see addendum)
- [Asahi Linux SEP documentation](https://asahilinux.org/docs/hw/soc/sep/) -- M-series-specific (T8112/M2 addresses); confirms the on-die IOP-mailbox architecture, not A-series coverage
- [Asahi Linux Progress Report: Linux 7.2](https://asahilinux.org/2026/08/progress-report-7-2/) (2026-08) -- checked directly, no SEP/Touch-ID/Omarchy mention
- [omarchy-mx-mac](https://github.com/maralcbr/omarchy-mx-mac) -- describes its GPU acceleration as running through Asahi's own Mesa `vulkan-asahi` driver, not a new one
