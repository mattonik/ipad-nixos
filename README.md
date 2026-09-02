# iPad NixOS

Run Linux on old iPads (2011–2017) via the checkm8 bootrom exploit, turning e-waste into usable Linux machines.

## What This Is

A reproducible build system that cross-compiles a Linux kernel and minimal NixOS userland for iPad hardware. PongoOS USB control and one RAM-only payload transfer are verified on the iPad Air 2, but Linux has not booted: stock PongoOS has no supported A8X handoff. See [the live project status](docs/project-status.md).

**Primary target:** iPad Air 2 (A8X, 2014) — 3-core ARM64, 2GB RAM, 2048x1536 Retina display.

**Research scope:** checkm8 covers ARM64 iPads with A7–A11 chips, but no device beyond the iPad Air 2 target has been tested. See [research/compatibility-matrix.md](research/compatibility-matrix.md) for the list.

## How It Works

```
checkm8 exploit → pongoOS → Linux 6.19 kernel → NixOS initramfs (in RAM)
```

1. **checkm8** — permanent, unpatchable bootrom exploit ([CVE-2019-8900](https://nvd.nist.gov/vuln/detail/CVE-2019-8900)) for Apple A5–A11 SoCs
2. **pongoOS** — pre-boot environment loaded via checkm8, provides USB protocol for uploading payloads
3. **Linux kernel** — cross-compiled for aarch64 with 16KB pages and Apple-specific drivers (touch, SPI, USB, framebuffer)
4. **NixOS initramfs** — minimal root filesystem running entirely from RAM; it is archive-verified but not yet reached on hardware

The boot is **tethered** — the iPad must be connected to a host computer via USB and re-flashed on every power cycle (~30 seconds).

## Quick Start

### Prerequisites

- NixOS/Linux with [Nix](https://nixos.org/download), or macOS with a configured Linux builder
- x86_64 Linux build target (the kernel and initramfs cross-compile to aarch64)
- iPad Air 2 + Lightning-to-USB cable

### Build

```bash
# Clone
git clone https://github.com/mattonik/ipad-nixos.git
cd ipad-nixos

# Build kernel (~4-5 hours first time, cached after)
nix build .#packages.x86_64-linux.kernel -o result-kernel

# Build initramfs with a local public SSH key (~5 minutes)
IPAD_AUTHORIZED_KEYS="$PWD/keys/builder_ed25519.pub" \
  nix build --impure .#packages.x86_64-linux.initramfs -o result-initramfs

# Compress kernel for pongoOS
xz --format=lzma -z -k -9 -c result-kernel/Image > boot/Image.lzma

# Build device tree pack (iPad Air 2)
./boot/mkdtbpack.sh boot/dtbpack \
  J81:result-kernel/dtbs/apple/t7001-j81.dtb \
  J82:result-kernel/dtbs/apple/t7001-j82.dtb
```

### Boot status

Do not use `flash.sh` as a working-boot recipe yet. The first payload
handoff returned to PongoOS before Linux ran, and the current J81 DTB has no
USB device-controller node, so USB Ethernet and SSH cannot work. Follow the
evidence-backed next step in [the live project status](docs/project-status.md).

## Project Structure

```
ipad-nixos/
├── flake.nix              # Nix flake — kernel + initramfs build targets
├── kernel/
│   └── default.nix        # Linux 6.19.3 config (16KB pages, Apple drivers)
├── nixos/
│   ├── initramfs.nix      # Minimal RAM-only rootfs (BusyBox + dropbear SSH)
│   └── initramfs-approaches.nix  # Documented alternative approaches
├── boot/
│   ├── flash.sh           # Automated boot script (checkm8 → pongoOS → Linux)
│   ├── load_linux.py      # pongoOS USB kernel uploader
│   ├── mkdtbpack.sh       # Device tree container builder
│   ├── extract-firmware.sh # WiFi/touch firmware extractor (from IPSW)
│   ├── Pongo.bin          # pongoOS v2.6.1 binary
│   └── gaster.nix         # Nix derivation for checkm8 exploit tool
├── research/              # Feasibility analysis and hardware documentation
│   ├── landscape.md       # Existing projects analysis (checkm8, pongoOS, etc.)
│   ├── hardware.md        # iPad Air 2 hardware mapping (SoC, peripherals)
│   ├── boot-chain.md      # Full boot path documentation
│   ├── driver-gap.md      # Driver status matrix per subsystem
│   ├── feasibility.md     # Go/no-go assessment
│   ├── touch-deep-dive.md # BCM5976 touch controller reverse engineering
│   ├── touch-re.md        # Z2 protocol and HID-over-SPI analysis
│   └── compatibility-matrix.md  # All 40 checkm8-vulnerable iPads mapped
├── docs/plans/            # Implementation plans
├── devenv.nix             # Dev shell (RE tools, USB tools, serial)
└── CLAUDE.md              # AI assistant context
```

## Supported Hardware

### Verified

| Device | SoC | Board ID | DTB | Status |
|--------|-----|----------|-----|--------|
| iPad Air 2 (WiFi) | A8X (T7001) | J81 | `t7001-j81.dtb` | Payload transferred; PongoOS handoff port required |
| iPad Air 2 (Cellular) | A8X (T7001) | J82 | `t7001-j82.dtb` | Untested |

### Expected Compatible (same boot chain, untested)

All ARM64 iPads with A7–A11 chips. See [research/compatibility-matrix.md](research/compatibility-matrix.md) for:
- iPad Air (A7)
- iPad Mini 2/3/4
- iPad 5th/6th/7th gen
- iPad Pro 9.7"/12.9" (1st gen)
- iPad Pro 10.5"/12.9" (2nd gen)

## Kernel Configuration

Linux 6.19.3 with key options for Apple hardware:

| Feature | Config | Purpose |
|---------|--------|---------|
| 16KB pages | `ARM64_16K_PAGES` | Required by Apple SoCs |
| Apple drivers | `COMPILE_TEST` | Unlocks drivers gated on `ARCH_APPLE` |
| Touch | `TOUCHSCREEN_APPLE_Z2` | BCM5976 via Z2 protocol over SPI |
| SPI | `SPI_APPLE` | Apple SPI controller (same A7–M4) |
| Display | `DRM_SIMPLEDRM` | Framebuffer initialized by pongoOS |
| USB | `USB_DWC2` | Synopsys DWC2 OTG (Lightning port) |
| USB Ethernet | `USB_CONFIGFS_ECM` | Host communication via USB gadget |
| Serial | `SERIAL_SAMSUNG` | Apple UART (Samsung S3C compatible) |
| WiFi | `BRCMFMAC` | Broadcom BCM4354 (needs firmware) |
| Bluetooth | `BT_BCM` | Broadcom BCM4354 (needs firmware) |

Full config in [kernel/default.nix](kernel/default.nix).

## Initramfs

The initramfs is the entire root filesystem — there is no disk. Everything runs from RAM.

| Component | Size |
|-----------|------|
| BusyBox (static, musl) | ~1.3 MB |
| dropbear SSH | ~0.5 MB |
| kmod | ~0.3 MB |
| **Total (zstd compressed)** | **2.1 MB** |

Provides:
- USB gadget Ethernet (ECM) at 192.168.7.2
- dropbear SSH server (key-only auth)
- Framebuffer console on iPad display (getty on tty1)
- Serial console on Apple UART
- `modprobe` for loading WiFi/BT modules

## Boot Chain Details

```
┌─────────────┐    USB     ┌─────────────┐
│  Host PC    │◄──────────►│  iPad (DFU)  │
│  (x86_64)   │  Lightning │  A8X SoC     │
└──────┬──────┘            └──────┬───────┘
       │                          │
  1. gaster pwn              checkm8 exploit
       │                     enters pwned DFU
  2. irecovery -f Pongo.bin      │
       │                     pongoOS running
  3. load_linux.py               │
     -k Image.lzma          kernel loaded
     -d dtbpack              DTBs loaded
     -r initrd               initramfs loaded
     -c "cmdline"            │
       │                     bootl command
       │                          │
       │                     Linux boots
       │                     USB gadget creates usb0
       │                          │
  4. ip addr add             ◄── 192.168.7.2
     192.168.7.1/24               │
  5. ssh root@192.168.7.2   ──► SSH session
```

## Firmware Extraction

WiFi (BCM4354) and touch (BCM5976) require firmware blobs extracted from an iPad IPSW file. These cannot be redistributed.

```bash
# Download IPSW from https://ipsw.me/iPad5,3
# Then extract firmware:
./boot/extract-firmware.sh iPad_Restore.ipsw ./firmware
```

## Development Environment

```bash
# Enter dev shell with RE and USB tools
nix develop --no-pure-eval
# or: devenv shell

# Available tools: ghidra, radare2, libimobiledevice,
# libirecovery, picocom, dtc, python3
```

## Research

The `research/` directory contains detailed analysis of every subsystem:

- **[landscape.md](research/landscape.md)** — Analysis of 8 existing projects (checkm8, pongoOS, Sandcastle, postmarketOS, Asahi Linux, Corellium)
- **[hardware.md](research/hardware.md)** — Chip-level hardware identification for iPad Air 2 (SoC, display, touch, WiFi, sensors)
- **[boot-chain.md](research/boot-chain.md)** — 12-step boot sequence documentation
- **[driver-gap.md](research/driver-gap.md)** — Per-subsystem driver status and effort estimates
- **[feasibility.md](research/feasibility.md)** — Go/no-go assessment and roadmap
- **[touch-deep-dive.md](research/touch-deep-dive.md)** — BCM5976 Z2 protocol analysis across 5 independent implementations
- **[compatibility-matrix.md](research/compatibility-matrix.md)** — All 40 checkm8-vulnerable iPad models

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is needed:
- **Hardware testing** — boot on different iPad models and report results
- **Device trees** — improve/fix DTBs for specific board IDs
- **Touch driver** — test and debug `apple_z2` on real hardware
- **WiFi firmware** — document extraction process for different iPad models
- **GPU** — PowerVR GXA6850 has no open-source driver; any Mesa/PVR work is valuable
- **NixOS modules** — build out the userland (GUI, networking, power management)
- **Documentation** — improve guides, add troubleshooting

## Prior Art and Credits

This project builds on the work of:
- [checkm8](https://github.com/axi0mX/checkm8) by axi0mX — bootrom exploit
- [checkra1n / pongoOS](https://github.com/checkra1n/PongoOS) — pre-boot environment
- [Konrad Dybcio](https://github.com/konradybcio) — first Linux boot on iPad Air 2 (June 2022)
- [Asahi Linux](https://asahilinux.org/) — Apple Silicon Linux (different SoCs, shared driver work)
- [Corellium](https://corellium.com/) — published Apple SPI/touch controller research
- [Nick Chan](https://github.com/asdfugil) — Apple device tree patches

## License

MIT — see [LICENSE](LICENSE).
