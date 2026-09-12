# J81 native GPU, audio, suspend, charging and storage plan

Updated 2026-09-10. Target: iPad Air 2 Wi-Fi, J81 / T7001 (A8X).

## Answer at a glance

These five items are not equally distant. Internal storage now has a concrete
Hoolock ANS1 implementation to test. Charging control and suspend have usable
Linux frameworks but still need J81-specific hardware control. Audio needs a
new old-Apple ASoC path. Native graphics needs both an A8X GPU port and a
display/KMS driver, making it the largest project.

| Item | First useful milestone | Main missing work | Relative distance |
| --- | --- | --- | --- |
| Internal storage | Repeatable, read-only `/dev/asp0n0` reads | Integrate Hoolock's ANS1 Linux and m1n1 branches, then harden the WIP block driver | Closest of these five |
| Charging policy | Report cable/charge state and enforce a conservative current limit | Identify the `charger,k48` control protocol, add a power-supply driver and connect it to battery/USB/thermal state | Medium/high |
| Suspend | Reliable suspend-to-idle with Power-button wake | Finish device power ownership, add driver PM callbacks and a T7001 CPU-idle path | Medium/high; deep suspend is longer |
| Audio | Headphone playback at a fixed safe level | Old Apple I2S/DMA, CS42L81 codec control and an ASoC machine description | High |
| Native GPU | A render node that completes a small off-screen workload | Exact GPU identity, DART, clocks/power, firmware and an A8X port of the PowerVR DRM/Mesa stack | Highest |

The practical order is internal storage read-only, charging observation and
control, suspend-to-idle, headphone audio, speaker audio, then GPU. Suspend
work should begin early as an audit because every new driver must eventually
implement suspend/resume, but deep system sleep should wait until device power
ownership is correct.

## Evidence from the J81

The private raw J81 ADT remains ignored and must not be committed. A sanitized
inspection confirms these relevant nodes and compatible strings:

- the GPU is `sgx`, compatible with `gpu,t7001`, and has GPU power-state and
  power-domain data;
- audio exposes `audio-control,cs42l81`, two MAX98721 speaker paths, the older
  T7001 I2S switch and routes for codec, speaker, voice and Bluetooth voice;
- internal storage is an `ans` storage coprocessor with an ANS nub and its own
  power gate;
- charging exposes `charger,k48`, a `function-set_charger` callback to the
  D2207 PMU and a device-specific charge curve.

Those names prove that the hardware paths exist. They do not define safe
register programming. Per-device calibration, identifiers, firmware and the
raw charge/speaker curves stay private.

## Native GPU acceleration

### Current state

Linux currently displays the bootloader framebuffer through `simplefb`; there
is no J81 DRM/KMS or GPU node. Hoolock marks both the A8X display pipe and GPU
as TBA. The pinned kernel contains the upstream Imagination PowerVR DRM driver,
but that driver documents only AXE-1-16M, BXM-4-64 and BXS-4-64 as supported.
Mesa has partial support for one GX6250 Series6XT BVNC, but explicitly warns
that other Series6XT variants can lack features and workarounds. Marketing
names such as GX6850/GXA6850 are insufficient: the exact BVNC must be read from
the hardware or recovered from Apple's driver data.

### What is needed

1. Decode a sanitized GPU resource map from the J81 ADT: all MMIO regions,
   interrupts, GPU DART/IOMMU, clocks, reset and PMGR domains. Add a disabled
   DT node first and verify that it owns no resources while disabled.
2. Read the GPU identity/BVNC without submitting work. Compare its feature and
   errata tables with Mesa's Series6XT device information. This is the gate for
   deciding whether upstream `drm/imagination` can be extended or whether the
   Apple command/firmware interface differs too much.
3. Bring up the GPU DART before enabling DMA. Then implement the Apple platform
   sequence: power domain, clocks, reset, firmware loading, address spaces,
   interrupts and recovery after a fault.
4. Extend the kernel PowerVR driver for the exact J81 BVNC and Apple platform
   quirks. Extract any required firmware locally from the matching IPSW; do
   not commit it.
5. Add the matching Mesa device information and workarounds. The first target
   is a render-only `/dev/dri/renderD128` and a small off-screen job with
   repeatable output. Keep simplefb for scanout during this stage.
6. Treat native display as a second driver project: implement the A8X display
   pipe, framebuffer allocation/import, vblank, modesetting, panel timing and
   backlight integration. Only then can a compositor page-flip GPU-rendered
   buffers normally.

### Acceptance gates

- Repeated power-on/off and deliberate bad submissions recover without a
  kernel hang or DART fault storm.
- Off-screen clears/copies produce stable checksums before any display work.
- KMS preserves the panel across mode changes and suspend/resume.
- Mesa reports the exact BVNC and passes focused rendering tests without
  corruption.

This work does not block a useful tablet: llvmpipe plus the existing
framebuffer can run a lightweight UI first.

### Wide ecosystem check, 2026-09-12: nothing to leverage yet

Checked directly (not from memory) whether anything in the broader
PowerVR/Apple-Linux ecosystem has moved since this section was last written,
specifically looking for anything reusable for GXA6850:

- **Mesa 25.3 added device-info/firmware entries for more Series6XT
  variants**, including `GX6650` (the official 6-cluster part closest to our
  8-cluster custom `GXA6850`) and a second `GX6250` BVNC. This is scaffolding,
  not usable support: Mesa's own docs (checked live) still list `GX6650` as
  "unsupported and not under active development", and even the
  *better*-supported `GX6250` BVNC (`4.40.2.51`) carries an explicit warning
  that "instability and corruption are to be expected." Confirms this
  section's existing point that even the closest official relative is not a
  working reference yet -- it just now also has a firmware/device-info
  placeholder, which is a real but small step (it means the pattern for
  *adding* a new BVNC is now demonstrated twice, which will matter once
  GXA6850's own BVNC is identified).
- **`drm/imagination`'s own upstream activity in 2026** (MT8173/`GX6250`
  support patches, July 2026) is the same story: incremental BVNC additions,
  none Apple-related, all still gated at "experimental."
- **Imagination's own vendor roadmap has moved away from this hardware
  generation entirely**, not toward it -- their official open-source driver
  page is now talking about their newer "Volcanic" architecture, with no
  stated interest in broader legacy Rogue/Series6XT support. Nothing to wait
  for from the vendor side.
- **The A7-A11 device tree patches already cited above are unchanged** --
  confirmed directly they are the same 2024-era posting (still "out for
  review," never merged), and confirmed they explicitly do not touch
  GPU/display at all, only SMP/UART/framebuffer/watchdog/timer/pinctrl/AIC.
- **No project anywhere targets `GXA6850` or Apple's PowerVR-era A-series
  GPUs specifically.** All serious Apple-GPU reverse-engineering (Asahi
  Linux) targets AGX, Apple's own in-house architecture that *succeeded*
  PowerVR licensing starting around A11/M1 -- a different vendor's IP than
  our Imagination-licensed GXA6850, despite occasional noted conceptual
  lineage (tiler-based rendering, general command-stream shape) between the
  two. That lineage is not a code-reuse path; it wasn't one for Asahi either,
  which still had to reverse-engineer AGX's actual ISA from nothing.
- **Project Cascadia** (A5 -> A6 -> A12/A13, a different community effort
  from Hoolock) is still in Phase 1 (kernel output/panic diagnosis, no
  framebuffer yet) and targets the A5's `SGX543MP2` -- PowerVR's older SGX
  family, not Rogue/Series6XT. No overlap with GXA6850 even if it matures.

**Conclusion: no update to this section's plan or its "Highest" distance
rating.** The concrete next step is still BVNC identification (this doc's
step 2 above), and there is still nothing published anywhere to compare that
BVNC against once found, beyond the same four production-quality reference
BVNCs and the two now-scaffolded-but-unstable Series6XT ones. Given how
slowly this specific niche moves and that the vendor itself has
deprioritized it, a good re-check cadence is "alongside major Mesa/kernel
release cycles" (roughly every few months) rather than more often.

## Audio

### Current state

The J81 ADT gives a concrete topology, but neither the pinned Hoolock tree nor
current upstream Linux contains CS42L81 or MAX98721 codec drivers. The Apple
MCA and ADMAC drivers in current Linux target the newer Apple Silicon audio
architecture and are references, not compatible T7001 implementations.

### What is needed

1. Decode the J81 audio graph without publishing calibration: I2S controller
   registers/IRQs, DMA channels, clocks, power domains, I2C addresses, GPIOs
   and the route between CS42L81, headphone/microphone paths and both speaker
   amplifiers.
2. Extract and inspect the matching iOS audio driver locally to determine the
   old I2S-switch register layout and the safe codec/amp initialization order.
   Start with read-only chip-ID/status accesses where the hardware permits it.
3. Add the minimum ASoC pieces:
   - a T7001 CPU DAI/I2S driver;
   - its DMAengine PCM path or an old-Apple audio DMA driver;
   - a regmap-based CS42L81 codec driver;
   - a J81 machine driver or audio-graph description for clocks and routes.
4. Prove headphones first at a fixed low level: clock generation, silent
   playback, a low-amplitude tone, stream start/stop and jack detection.
5. Add MAX98721 control only after its reset/mute sequence and per-device
   calibration format are understood. Keep both amplifiers muted by default
   and apply a conservative gain ceiling.
6. Add microphones, automatic routing and PipeWire policy after playback is
   stable. Speaker EQ and protection can follow the Asahi pattern, but Asahi's
   profiles are for Apple Silicon Macs and cannot be reused as J81 tuning.

### Acceptance gates

- No pop or DC transient during probe, playback, shutdown or reboot.
- Headphone playback survives repeated start/stop before speaker power is
  enabled.
- Speaker output is temperature/current monitored, calibrated and capped.
- Audio devices suspend and resume without leaving an amplifier powered.

## Suspend

### Current state

The CPU nodes use `enable-method = "spin-table"`; there is no PSCI firmware
node, CPU idle-state description or T7001 platform suspend implementation.
The working boot also uses `pd_ignore_unused clk_ignore_unused` because Linux
otherwise turns off domains needed by the inherited display. Those flags are
useful for bring-up but prevent meaningful system power reduction.

### What is needed

Build suspend in three stages:

1. **Runtime PM and ownership.** Describe the real clock and power-domain
   consumers, add runtime PM to each active driver and remove the two ignore
   flags only when the screen, USB and shell survive. Measure idle current
   after each domain is released.
2. **Suspend-to-idle.** Enable the kernel suspend path, make every enabled
   driver quiesce DMA/IRQs and resume cleanly, and keep a known wake source
   armed. The Power button is the first wake source; RTC wake can follow.
   USB networking will disappear during a successful suspend, so use UART or
   a reserved-memory/pstore trace to distinguish suspend, wake and resume
   failures.
3. **Deep suspend.** Implement the T7001 CPU/cluster and PMGR entry/resume
   sequence, AIC and timer save/restore, secondary-CPU park/release, DRAM
   retention and a physical resume trampoline. The clean interface is either
   a small T7001 Linux platform backend or resident m1n1 firmware services
   modelled after PSCI. The current m1n1 build exposes no PSCI path, so simply
   adding `idle-states` to DT is insufficient.

### Acceptance gates

- Fifty suspend-to-idle cycles wake by Power button with working display,
  input and USB after resume.
- Idle current drops measurably when runtime-managed domains turn off.
- Deep suspend preserves RAM and time, rejects unsafe entry when a driver is
  busy, and recovers every enabled device.

Suspend-to-idle is the useful first target. Deep suspend is a separate SoC
power-management project and should not be attempted while clocks and domains
are globally pinned on.

## Charging policy

### Current state

The read-only fuel-gauge path now works across a permanent reboot: the BQ27545
reports stable voltage, current, temperature, capacity and cycle count through
UART5/HDQ. It cannot enable, limit or terminate charging. The ADT compatible
`charger,k48` names an older Apple charger-policy interface; its
`function-set_charger` phandle resolves to the D2207 PMU at I2C address `0x3c`,
rather than a separate charger IC or HDQ mux.

The 2026-09-10 Apple-driver review identifies the first useful register set,
independently matched in iOS 10.3 s8000 and T8010 `AppleD2207PMU` builds:

| Register | Apple-driver meaning | Live J81 value |
| --- | --- | --- |
| `0x0050`--`0x005d` | 14-byte event block | Captured privately; bits still need semantic names. |
| `0x0060`--`0x006c` | 13-byte status block | `0f 03 42 20 7e 00 00 00 00 00 00 00 03` across repeated reads. |
| `0x0010` bit 2 | USB input-current suspend | Clear (`0x00`), so the input is not explicitly suspended. |
| `0x04c0` | USB input-current setting | `0x02`, decoded by Apple's own conversion as 100 mA. |
| `0x04c6` | Charge-current setting, 50 mA/count | `0x3c`, or 3,000 mA configured. |
| `0x04c7[5:0]` | Hardware charge-current ceiling | `0x3f`, or 3,150 mA. |
| `0x04cf[5:0]` | Configured maximum charge current | `0x3c`, or 3,000 mA. |
| `0x04c8` bit 3 | Charge-timer reset control | Identified; no write attempted. |

The same driver exposes ADC channels for VBUS voltage (19), VBUS current (9),
battery voltage (4), battery temperature (2), and system voltage (0). Its
reported maximum USB input current is 3,262 mA. Charge-voltage programming is
explicitly unsupported in this implementation.

The permanent-boot direct USB network session shows the same behavior: the
battery is healthy and present, but net current is about -0.63 A and status is
`Discharging`. The PMIC still reports input code `0x02` (100 mA), while the
charge-current ceiling remains 3,000 mA. The low input limit is consistent with
the running system load exceeding what the PMIC permits, so the cable sustains
networking while the battery drains. This is an inference from the two
measurements; a USB power meter and cable A/B run remain the acceptance test.

The Apple D2207 power-source disassembly also makes the input-limit conversion
precise. For non-suspended targets from 75 mA through 3,261 mA it selects the
raw code `floor((8 * target_mA - 600) / 100)`, and the reverse readback is
`75 + floor((100 * code + 7) / 8)`; the PMIC status register `0x0010` bit 2 is
set when the requested target is below 75 mA. The reference maximum is 3,262
mA. Therefore 500 mA would be raw code `0x22`, not `0x0a`. The reference setter
writes the status bit and `0x04c0` as one operation, which gives us a safe
implementation contract but does not yet prove that the current Mac cable or
wall charger can supply the requested current.

The same disassembly identifies read-only charger state inputs: the 13-byte
status block at `0x0060`--`0x006c`, VBUS voltage ADC channel 19 and VBUS current
ADC channel 9. On the current data-host boot, status byte `0x0062` is `0x42`;
its USB-power-limited bit (bit 5) is clear, and the event/status blocks are
stable across repeated reads.

No charger register was written. The PMIC is bound to the existing
`arabela-pmic` regmap; direct non-forced I2C access correctly reports the
address busy. Exact read-only follow-up values and the full session snapshot
are kept under ignored `artifacts/live/`, not committed.

#### CHG-1 implementation checkpoint (2026-09-10)

The tree now contains a J81-specific, read-only `apple,j81-d2207-charger`
power-supply child. It reuses the PMIC's existing regmap and exposes only
`input_current_limit` from `0x04c0` and
`constant_charge_current_max` from `0x04cf`, using microamp units and the
Apple conversion above. There is no `set_property` callback, so this child
cannot write the PMIC. The DT child, Kconfig, Makefile entry and driver are
kept in `kernel/patches/0010-j81-d2207-readonly-charger.patch` and enabled in
the Hoolock kernel configuration.

The patch applies cleanly in the full Nix kernel build. The resulting Nix
kernel output is `/nix/store/2jbq34ia5rjyrwq5hsrr3z76yk534vq3-linux-aarch64-unknown-linux-gnu-7.3.0-rc1`;
the J81 `Image` SHA-256 is
`3a40e7a2ff4bcb20e5109a82df7524f72c28f76ad5e2b1a978b3bda210bbbe9c` and the
J81 DTB SHA-256 is
`8bfa7958053ec54c941eb294c97731231e0bc6eea6d553a0e1250d5cc7ccdc09`.
The conversion self-check passed for 100 mA, 500 mA, 3,000 mA and 3,150 mA.
The integrated Hoolock control payload also built successfully at
`/nix/store/zbha9gnq18agj6apl5sni1m8gwiqxyym-ipad-air2-m1n1-hoolock-control`;
its `Image.gz` SHA-256 is
`7354e8a9e98d4ff9a5d0246ea03bbe5773ace0d4b54b17658d95b43604b24df2`, its
J81 DTB SHA-256 is
`bc94c94222dd967f345a4d7d18f6ae4e036d6b54339db551ff9d240e703fcd01`, and
the packaged `m1n1-linux.bin` SHA-256 is
`b8d7a2e99c568277947d9f219bff92c2476e532956302ae63806c9de8611f271`.
It has not yet been booted on J81, so sysfs registration and cable behavior
remain hardware test work. The existing battery path is unchanged, and no
PMIC register was written during implementation, build validation or payload
packaging.

Validation commands were:

- `nix build .#packages.x86_64-linux.hoolock-kernel -o result-hoolock-kernel -L`
- `nix build .#packages.x86_64-linux.m1n1-hoolock-control -o result-hoolock-charger-payload -L`
- the inline D2207 conversion assertions recorded above

Both builds passed on the remote Linux builder. The build logs included the
known cache-DNS retry warning and the existing Hoolock DT decompile warnings
(simple-bus unit formatting and placeholder phandle checks); neither stopped
the build or came from the new charger driver.

### What is needed

1. Boot this read-only child and confirm its two sysfs values match the raw
   PMIC reads, then use a USB power meter to record the D2207 status block,
   input-current setting, gauge current and VBUS measurements for disconnected,
   Mac data, and known charger cases. This assigns semantic names to the status
   bits without guessing and shows who changes `0x04c0`.
2. Extend the child only with independently verified properties: `ONLINE`,
   `STATUS` and fault/thermal state after the cable A/B table identifies their
   bits. Use Linux's standard power-supply units (microamps and microvolts)
   and cross-check every value against the gauge and meter.
3. Add one conservative write at a time: disable charging, low input-current
   limit, low charge-current limit, termination voltage, then enable. Encode
   hard maximums in the kernel from verified hardware data; do not accept
   arbitrary raw register values from userspace.
4. Connect USB/Lightning current capability, gauge temperature/SOC and thermal
   limits. Loss of communication, over-temperature, over-voltage or an
   unknown cable state must disable charging or fall back to the verified safe
   hardware state.
5. Add optional userspace policy, such as an 80% charge target, only after the
   kernel driver safely owns the hardware. Kernel code remains responsible for
   electrical and thermal safety; userspace chooses targets within those
   limits.

### Acceptance gates

- Plug/unplug and charge/discharge direction agree across the charger, gauge
  and external meter.
- A low current limit is measurable, survives reconnect and fails safe.
- Thermal cutoff and restart hysteresis work under a controlled test.
- Suspend does not leave the charger in an unbounded or stale state.

## Internal NAND storage

### Current state and corrected conclusion

J81 storage is not a raw NAND/MTD problem. The ANS1/ASP coprocessor and its
firmware provide the flash translation layer and expose block commands.
Hoolock now labels A8/A8X internal storage WIP and has matching experimental
branches:

- Linux `ans1` at `ed8528f` is 27 commits ahead of the project's pinned
  `6831bc7` base. It adds old RTKit protocol support, 64-bit AKF mailbox
  support, the ANS1 binding, T7001 nodes and `drivers/block/asp.c`.
- m1n1 `ans1` contains commit `9d53672`, which passes Linux the ANS firmware
  region that iBoot already loaded. The project's current m1n1 binary is from
  the `idevice` branch at `d5a10ac` and lacks that commit.

This is the closest real implementation path among these five items. It is
still dangerous WIP code: the driver enables user-area writes during probe,
contains `BUG()`/`BUG_ON()` assertions, has timeout recovery disabled, and
states that an RTKit crash cannot recover without reboot because firmware came
from the previous boot stage.

### What is needed

1. Add a separate experimental payload pinned to Linux `ed8528f` and a
   reproducibly built m1n1 containing `9d53672`. Preserve the current known-good
   USB payload for recovery and comparison.
2. Before the first boot, patch ASP into observation-only mode:
   - remove the `WRITE_UNLOCK` command;
   - reject all block writes and flushes that can mutate media;
   - mark the user area and every auxiliary namespace read-only;
   - replace reachable fatal assertions with errors that offline the disk;
   - omit any format path from the test build.
3. Confirm that m1n1 creates the reserved firmware-memory entry and that the
   Linux DT has the T7001 ANS mailbox, power domain, reset and firmware region.
4. Boot from RAM and require only `ASP is alive`, identify/capacity and block
   enumeration. Read a few aligned 4 KiB sectors twice and compare hashes.
   Never mount APFS read-write.
5. Add timeout handling that freezes/offlines the disk and returns I/O errors.
   Since firmware cannot currently be reloaded, controller recovery can
   require a reboot, but it must not panic the kernel or leave requests hung.
6. After repeated read-only tests, inspect the partition map offline. Expect
   iOS user data to remain encrypted without the SEP/keybag path. Persistent
   Linux storage will require a deliberately allocated partition or other
   non-destructive layout; it does not make the checkm8/PongoOS boot chain
   persistent by itself.
7. Enable writes only on disposable media or a deliberately created Linux
   area after backup/recovery testing, flush/FUA validation, power-cut tests
   and bounds checks. Keep firmware, SysCfg and all auxiliary namespaces
   permanently read-only.

### Acceptance gates

- `blockdev --getro /dev/asp0n0` reports read-only before the first read.
- Repeated sector reads match and produce no RTKit crash, DART fault or media
  mutation.
- Timeouts return I/O errors and leave the rest of Linux reachable over USB.
- Write support is not considered ready until power-cut and recovery tests pass
  on data that can be lost.

## Dependency-ordered execution plan

1. Keep the permanent battery fix as the measurement baseline for charging and
   suspend work; complete warm/cold and iPadOS comparison when convenient.
2. Build the ANS1 experimental payload with the read-only hardening patch and
   test enumeration from the RAM-root system.
3. Reverse engineer charger status, then implement read-only reporting and one
   conservative control at a time.
4. Audit clock/power ownership and driver PM callbacks; prove runtime PM and
   suspend-to-idle.
5. Implement audio through headphones before touching speaker amps.
6. Begin GPU identity/DART research independently, but keep implementation
   behind storage, charging, touch and local networking because software
   rendering already supplies a usable fallback.
7. Attempt deep suspend after active drivers all pass suspend-to-idle; add
   native display/KMS after render-only GPU execution works.

## Primary sources

The working copies of the two `AppleD2207PMU` binaries used for the symbol and
disassembly cross-check remain local research artifacts and are not committed;
their public source artifacts are linked below.

- [Hoolock A8/A8X support matrix](https://github.com/HoolockLinux/docs/blob/master/features/A8.md)
- [Hoolock Linux ANS1 branch](https://github.com/HoolockLinux/linux/tree/ans1)
- [Hoolock ANS1 block driver](https://github.com/HoolockLinux/linux/blob/ans1/drivers/block/asp.c)
- [Hoolock ANS1 DT binding](https://github.com/HoolockLinux/linux/blob/ans1/Documentation/devicetree/bindings/block/apple,s5l8960x-ans.yaml)
- [m1n1 ANS1 firmware handoff](https://github.com/HoolockLinux/m1n1/commit/9d53672dbf5f41577aaa182284f68d06614e2dcf)
- [Upstream Apple ANS2 NVMe driver](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/apple.c)
- [Upstream PowerVR DRM supported cores](https://docs.kernel.org/gpu/imagination/index.html)
- [Mesa PowerVR hardware status and BVNC requirement](https://docs.mesa3d.org/drivers/powervr.html)
- [PowerVR DT binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/gpu/img,powervr-rogue.yaml)
- [Linux device power-management model](https://github.com/torvalds/linux/blob/master/Documentation/driver-api/pm/devices.rst)
- [Linux power-supply class and units](https://docs.kernel.org/power/power_supply_class.html)
- [Unstripped iOS 10.3 s8000 AppleD2207PMU kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleD2207PMU.kext)
- [Unstripped iOS 10.0 T8010 AppleD2207PMU kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.0/T8010/AppleD2207PMU.kext)
- [Asahi userspace audio and speaker-safety model](https://github.com/AsahiLinux/asahi-audio)
- [Corellium SN2400 charger prior art](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/sn2400-charger.c)
- [Corellium mobile NVMe prior art](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/nvme/host/hx.c)
