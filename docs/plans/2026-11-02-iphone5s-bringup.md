# iPhone 5s (A7) bring-up plan

Date: 2026-11-02. Status: plan plus first payload, nothing run on hardware.

Goal: reach the same milestone the iPad Air 2 reached on 2026-09-08, a Linux
shell on the iPhone 5s that the Mac can reach over USB networking
(`172.16.42.1`, telnet), using this repository's existing Nix tooling and boot
scripts. Nothing here touches the J81 payloads or patches.

## The device

| | iPhone 5s | iPad Air 2 (for comparison) |
|---|---|---|
| SoC | Apple A7, S5L8960X, CPID `0x8960` | A8X, T7001, CPID `0x7001` |
| CPU | 2x Cyclone, 1.3 GHz | 3x Typhoon, 1.5 GHz |
| RAM | 1 GB | 2 GB |
| Display | 640x1136, MIPI DSI | 1536x2048 |
| Last iOS | 12.5.8 | 15.8.x |
| Kernel pages | 4 KiB | 4 KiB |

There are two boards. Upstream's DTS files are identical except for the
`compatible` and `model` strings, so the choice only matters for naming and
for the ADT identity check:

| Board | Product | Model numbers | DTS |
|---|---|---|---|
| N51 | iPhone6,1 | A1453, A1533 | `s5l8960x-n51.dts` |
| N53 | iPhone6,2 | A1457, A1518, A1528, A1530 | `s5l8960x-n53.dts` |

**Open: which board Martin has.** Asked on 2026-11-02.

A7 is the first chip of the same family as A8X. Most SoC blocks share
drivers and compatibles: our T7001 nodes often carry
`apple,s5l8960x-*` as the fallback compatible, and Hoolock's DART notes put
both chips in the same `dart,s5l8960x` variant.

## What carries over unchanged

Checked against the pinned inputs in `flake.nix` on 2026-11-02:

- **PongoOS.** `hoolockDocs/binaries/Pongo.bin` is Hoolock's universal build for
  A7 to A11. The same docs commit ships `binaries/im4m/0x8960.im4m` for the
  iBoot method.
- **m1n1.** The pinned Hoolock `idevice` m1n1 (`d5a10ac`) has A7 paths:
  Cyclone chicken bits (`chickens.c`), the spin-table start offset
  (`smp.c`, `CPU_START_OFF_S5L8960X`), cpufreq tables, the USB complex remap
  (`usb.c`), and a display special case for the 5s's native 640x1136 panel
  (`display.c`).
- **Kernel.** `hoolockKernel` is Hoolock's defconfig with 4 KiB pages, which
  A7 also needs. Its config already enables everything the 5s DTS uses:
  `ARCH_APPLE`, `I2C_APPLE`, `PINCTRL_APPLE_GPIO`, `APPLE_PMGR_PWRSTATE`,
  `USB_DWC2` (dual role) with `PHY_APPLE_AUSB`, `BACKLIGHT_APPLE_DWI`,
  `RTC_DRV_APPLE_PMIC`, `SPI_APPLE`. Our J81 patches only add T7001 DT nodes
  and drivers that bind to J81-only compatibles, so they are inert on A7.
  **No new kernel build is needed for the first boot.**
- **Device tree.** The pinned Hoolock tree (`6831bc7`) already has
  `s5l8960x-n51.dts` and `s5l8960x-n53.dts`, with UART0, I2C0 to I2C3, AIC,
  PMGR, watchdog, pinctrl, cpufreq, the USB complex (`usbdev@20c100000`,
  dwc2 peripheral plus AUSB PHY), DWI backlight, the Amber PMIC RTC at I2C
  `0x74`, and `gpio-keys` for Home, Power, Volume and the mute switch.
  Hoolock's feature table lists display, buttons and brightness as
  upstream for the iPhone 5s; USB device mode and RTC are in linux-apple.
- **The `framebuffer@0` rename.** Same m1n1 `dt_set_fb()` exact-path issue
  as J81, so the same `sed` fix applies. Verified on both DTBs (below).
- **Initramfs and USB gadget.** The postmarketOS debug initramfs and the
  `ecm.usb0` override are architecture-generic.
- **Host tools.** `boot/load_m1n1.py` (PongoOS `bootm`), `boot/dump_adt.py`
  (now takes `--board n51|n53`), the telnet workflow, and i2c-tools.
- **One driver of ours directly.** `kernel/patches/0007` (S5L SPI support in
  `spi-apple`) matches `apple,s5l8960x-spi`, the A7 controller variant. It is
  the starting point for 5s touch.

## What does not carry over

These parts are J81-specific and need fresh work on the 5s. Chip names
from public teardowns are leads only until the 5s ADT confirms them.

| Area | J81 state | iPhone 5s |
|---|---|---|
| PMIC and charging | Dialog D2207 at `0x3c`; RTC, backlight and charging all work | Different PMIC ("Amber", `apple,amber-pmic` at `0x74`). RTC is in DT. Charger registers have to be found again; the D2207 `0x04c0` work does not apply |
| Battery gauge | TI bq27xxx over HDQ on UART5, Linux frontend written | Unknown until ADT. Our `bq27xxx_battery_hdq_uart` frontend is reusable if it is the same HDQ-over-UART arrangement |
| Wi-Fi | BCM4350 on PCIe, `pcie-apple-t7000` driver | A different, older Broadcom part (teardowns say BCM4334-class). Expect SDIO rather than PCIe. None of our PCIe/DART/MSI work applies |
| Bluetooth | BCM on UART3 | Likely Broadcom on a UART again; the serdev and `hci_bcm` approach should carry |
| Touch | SPI3, Z2-style firmware upload, first ACK on 2026-11-02 | Broadcom/TI touch, likely also SPI and Z2-style; firmware and calibration come from the 5s's own ADT and IPSW |
| Storage | ANS1, read-only hardened patch | Hoolock lists A7 internal storage as WIP; not in scope early |
| Display | iBoot framebuffer | Same approach; native panel |

## Risks before the first boot

1. **checkm8 on this Mac with an A7.** Our working recipe is palera1n
   `--pongo-shell --override-pongo`. palera1n officially targets A8 to A11;
   whether its DFU exploit path works for CPID `0x8960` on an Apple Silicon
   Mac is unverified. Hoolock's own notes say A7 needs several replugs for the
   exploit to succeed on a Linux host. Fallbacks in order: checkra1n 0.12.4
   (supports A7 and has its own PongoOS shell and override options), then
   Hoolock's iBoot method (`remote_boot` with gaster, using
   `im4m/0x8960.im4m`), noting gaster has been unreliable on this Mac before.
2. **The PongoOS method needs a bootable iOS install.** Hoolock's setup guide
   says the PongoOS route only works when the device can boot its normal OS.
   The phone should have a working iOS 12.5.x before we start.
3. **No serial console.** UART0 needs a Lightning DCSD/Kong-style cable.
   As on J81, the screen and USB networking are the observation channels.
4. **1 GB RAM.** The debug initramfs is small, but anything beyond it
   (NixOS-in-RAM) has to be sized for half the iPad's memory.

## Steps to a USB shell

**P0, Martin, no code.** Model number (N51 or N53). iOS version, and confirm
it boots normally. Put it in DFU and confirm the Mac sees CPID `0x8960`.

**P1, payload (done in this branch, not built yet).**
`packages.x86_64-linux.m1n1-hoolock-n51-control` and `-n53-control`
(`mkIphone5sControl` in `flake.nix`). Same shape as `m1n1-hoolock-control`:
Hoolock `Pongo.bin`, the nightly m1n1 the J81 control payload uses,
`hoolockKernel`'s `Image`, the board's DTB with the framebuffer rename, the
debug initramfs with the `ecm.usb0` override and i2c-tools, and the same
bootargs (`pd_ignore_unused clk_ignore_unused` included). The build itself
fails if the renamed `/chosen/framebuffer` node or the board compatible is
missing. Building it only repackages the existing kernel output, so it costs
no kernel build when `hoolockKernel` is already in the builder's store.

Build on the Mac with:

```
nix build .#packages.x86_64-linux.m1n1-hoolock-n51-control -o result-n51
```

**P2, PongoOS and an ADT capture.** Boot to PongoOS with palera1n (or the
fallbacks above), then:

```
nix develop -c python3 boot/dump_adt.py --board n51
```

The capture goes to the Git-ignored `artifacts/adt/` and is private (serial
numbers and calibration). Record only sanitized facts and the hash. The ADT
answers the open hardware questions: Wi-Fi bus, gauge transport, touch
controller and SPI instance, Bluetooth UART, PMIC child functions.

**P3, first Linux boot.** From the PongoOS shell state:

```
python3 boot/load_m1n1.py result-n51/m1n1-linux.bin
```

`boot/run_m1n1_debug.sh` is not used here: it verifies a J81 private Wi-Fi
manifest. Pass criteria, in order: m1n1 output on screen; kernel console on
screen; the postmarketOS `/ #` prompt; the Mac sees USB `0525:a4a2` and an ECM
interface; `ping 172.16.42.1` and telnet work.

If it hangs at a black screen, reuse the J81 Round 3 to 5 method: change one
thing per boot, starting with `earlycon`/console placement and the
framebuffer node, not the kernel.

**P4, read-only inventory over the shell.** `dmesg`, `/sys/class/*`,
`i2cdetect -l`, and a read-only `i2cdump` of the Amber PMIC at `0x74`.
No PMIC writes until a register is understood, the same rule J81 followed.

## After the shell

Rough order, each with its own hardware gate:

1. Confirm what upstream already gives: buttons (`evtest`), backlight,
   RTC.
2. Battery gauge, then read-only charger observation on the Amber PMIC,
   then charging, mirroring CHG-1/CHG-2.
3. Touch on SPI, starting from `0007`.
4. Bluetooth over UART with serdev and `hci_bcm`.
5. Wi-Fi once the ADT says which bus. SDIO would need an Apple SDIO host
   driver, which neither we nor Hoolock have.
6. Storage, read-only first, following the ANS1 discipline.

## Firmware sources

The firmware archive thread is adding the iPhone 5s iOS 7.0 and 12.5.8 IPSWs
to `/Volumes/martin/Projects/Archive/ipad-nixos/firmware/ipsw/`. 12.5.8 is the
right source for the DeviceTree (cross-check against the live ADT) and the
kernelcache for Apple driver analysis (touch, PMIC, Wi-Fi). Keep extracted
firmware out of Git, as for J81.

## Verification done for P1

- Compiled `s5l8960x-n51.dts` and `s5l8960x-n53.dts` from the pinned Hoolock
  commit with `cpp` and `dtc` 1.8.1, applied the payload's `sed` rename, and
  checked both results: `/chosen/framebuffer` without a unit address,
  `"apple,n51"`/`"apple,n53"` present, `usbdev@20c100000` present. The
  unrenamed DTBs fail the build's check, as intended.
- `flake.nix` parses (`nix-instantiate --parse`). The full flake was not
  evaluated or built in the cloud session, because it cannot fetch the
  `github:` inputs. The first real build has to run on the Mac.
- `boot/test_dump_adt.py` covers the new board profiles and passes.
