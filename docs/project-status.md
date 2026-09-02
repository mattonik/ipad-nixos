# iPad Linux Project Status

Status date: 2026-09-02  
Target: iPad Air 2 Wi‑Fi A1566, A8X/T7001, board J81/J81AP  
Repository: [mattonik/ipadlinux](https://github.com/mattonik/ipadlinux)  
Upstream: [jacopone/ipad-nixos](https://github.com/jacopone/ipad-nixos)

## Mission

The project aims to turn old Apple tablets into useful, open Linux hardware.
The iPad Air 2 is the first reference platform and driver laboratory. We are
using it to develop and validate a complete Linux stack for Apple tablet
hardware, including the display, touchscreen, USB, USB networking, Wi‑Fi,
Bluetooth, storage, power management, device tree and Apple SoC support.

The longer-term goal is to carry that knowledge to newer iPad Pro hardware
with A12X/A12Z chips and eventually M-series iPads, with the ambition of
running a complete Arch-based system such as [Omarchy](https://omarchy.org/)
where the boot chain and hardware support make that possible.

The current checkm8/PongoOS boot path is a reference path for the A8X. It is
not expected to work unchanged on A12X/A12Z or M-series devices; those devices
will require separate boot research in addition to driver and kernel work.

## Intended final result

The practical end state is a reproducible, tethered Linux tablet:

```text
Mac/Linux host
    │
    └── checkm8 → PongoOS → Linux kernel → NixOS/Arch userspace
                                      ├── display and touchscreen
                                      ├── USB and USB networking
                                      ├── Wi‑Fi and Bluetooth
                                      └── local console and SSH
```

“Tethered” means the host computer is required to boot the iPad again after
power loss or a restart. The current design boots the kernel and initramfs
into RAM and does not replace or erase iPadOS storage. Persistence and a full
desktop distribution are later goals, not prerequisites for the first boot.

The project has two useful definitions of done:

1. **First technical success:** boot the custom Linux kernel and initramfs on
   the iPad Air 2.
2. **Platform success:** make the iPad a useful Linux hardware and driver
   development platform, then use the results to approach fully working Linux
   on newer Apple tablets.

## Boot chain

```text
checkm8 exploit
    ↓
PongoOS
    ↓
Linux 6.19.3 kernel
    ↓
J81 device tree
    ↓
NixOS initramfs in RAM
    ↓
USB Ethernet, console and SSH
```

- **checkm8:** bootrom exploit used to run an untrusted payload on the
  A8X.
- **PongoOS:** pre-boot environment that should expose a USB protocol for
  uploading the Linux payload.
- **Linux:** custom aarch64 kernel with Apple-specific support and 16 KB pages.
- **initramfs:** minimal statically linked musl/NixOS userspace with BusyBox,
  kmod and Dropbear SSH.

## What is complete

### Repository and workflow

- A personal GitHub remote is configured as `origin`.
- The original project is retained as the `upstream` remote.
- Logical portability and boot-flow changes are committed and pushed.
- VM images, VM configuration, SSH keys and generated build outputs remain
  local and are not committed.

### Build infrastructure

- Host: Apple Silicon M1 Mac running macOS 26.5.
- Nix: Determinate Nix 3.22.2 / Nix 2.35.2.
- Linux builder: `darwin.linux-builder-vz`, reachable through the configured
  Nix remote builder.
- Builder allocation: 4 CPUs, 8 GB RAM, 40 GB disk.
- The original platform mismatch was fixed so Linux packages build through the
  Linux builder rather than trying to build Linux-only derivations directly on
  Darwin.
- The kernel configuration was reduced to avoid unnecessary Rust and test
  builds and to keep the builder within its available resources.

### Build and boot artifacts

The required artifacts have been built successfully:

| Artifact | Location | Approximate size |
| --- | --- | ---: |
| Linux kernel | `result-kernel/Image` | 40 MB |
| J81 device tree | `result-kernel/dtbs/apple/t7001-j81.dtb` | 26 KB |
| LZMA kernel for PongoOS | `boot/Image.lzma` | 10 MB |
| Device-tree pack | `boot/dtbpack` | 26 KB |
| Initramfs | `result-initramfs/initrd` | 2.1 MB |
| PongoOS | `boot/Pongo.bin` | 248 KB |

The two original build milestones are therefore complete:

```bash
nix build .#packages.x86_64-linux.kernel -o result-kernel -L
nix build .#packages.x86_64-linux.initramfs -o result-initramfs -L
```

### Portability changes

- Darwin-compatible package definitions were added for the development shell.
- Native macOS gaster is built from upstream source.
- `boot/mkdtbpack.sh` no longer depends on GNU-only `stat -c` behavior.
- `boot/flash.sh` uses portable paths and no longer assumes `lsusb` exists.
- Python USB dependencies are available inside the Nix development shell.
- The boot script now handles the PongoOS upload and reconnect sequence more
  explicitly.

## Hardware progress

The iPad has been repeatedly identified correctly:

```text
CPID:    0x7001
PRODUCT: iPad5,3
MODEL:   j81ap
NAME:    iPad Air 2 (WiFi)
```

The following stages are proven:

- Fresh DFU mode can be entered.
- checkm8 exploitation succeeds.
- palera1n can reach `Checkmate!`.
- The Apple Silicon USB reconnect issue can be worked around by manually
  reconnecting the cable at the requested point.
- The custom `boot/Pongo.bin` is accepted and the iPad displays the
  chess-style PongoOS logo with tiny console text.

The successful run used the standalone arm64 palera1n CLI rather than the
3.0.0 beta GUI bundle:

```bash
sudo /tmp/palera1n-arm64 \
  --pongo-shell \
  --override-pongo "$PWD/boot/Pongo.bin" \
  --debug-logging
```

## Current blocker

Although PongoOS appears on the iPad, macOS does not see the expected PongoOS
USB interface:

```text
Vendor/product: 05ac:4141
```

Both checks currently fail:

```bash
irecovery -q
# ERROR: Unable to connect to device

python3 -c 'import usb.core; print(usb.core.find(idVendor=0x05ac, idProduct=0x4141))'
# None
```

`system_profiler SPUSBDataType` also showed no corresponding PongoOS device.

This means the kernel uploader cannot yet communicate with PongoOS. Linux has
not been uploaded or booted, and no SSH or USB Ethernet connection has been
established.

The remaining possibilities to investigate are:

- PongoOS USB gadget initialization on this iPad/cable/M1 macOS combination.
- Whether the checked-in PongoOS binary is compatible with this exact
  palera1n handoff.
- USB re-enumeration or driver behavior after the DFU-to-Pongo transition.
- Whether a known-good PongoOS build or PongoOS terminal utility sees the
  device when PyUSB does not.

This is a transport/handoff problem, not a kernel-build problem.

## Current state at a glance

| Stage | Status |
| --- | --- |
| Personal repository and remotes | ✅ Complete |
| Reproducible M1/Linux-builder workflow | ✅ Complete |
| Linux kernel build | ✅ Complete |
| Initramfs build | ✅ Complete |
| J81 DTB generation and packaging | ✅ Complete |
| macOS gaster and development shell | ✅ Complete |
| DFU detection | ✅ Complete |
| checkm8 exploit | ✅ Complete |
| PongoOS upload | ✅ Complete |
| PongoOS visible on iPad | ✅ Complete |
| PongoOS USB interface `05ac:4141` | ❌ Blocked |
| Linux payload upload | ❌ Not started successfully |
| Linux kernel boot | ❌ Not achieved |
| Display/touch/Wi‑Fi/Bluetooth validation | ❌ Not started |
| Usable tethered Linux tablet | ❌ Future milestone |

## Next technical step

Do not rebuild the kernel or use the palera1n GUI Start button. The next
experiment is to solve PongoOS USB enumeration while the iPad is showing the
PongoOS logo. Once `05ac:4141` appears, use the existing uploader:

```bash
sudo -E env "PYTHONPATH=$PYTHONPATH" python3 boot/load_linux.py \
  -k boot/Image.lzma \
  -d boot/dtbpack \
  -r result-initramfs/initrd \
  -c "console=tty0 earlycon loglevel=7 root=/dev/ram0"
```

The first Linux boot is intentionally modest: prove the kernel starts, get a
console, bring up USB networking, and connect over SSH. Driver and desktop
work comes after that baseline is reliable.

## Safety boundaries

- Do not restore the iPad through Finder or the macOS DFU warning.
- Do not use palera1n rootful/rootless jailbreak options for this project.
- Do not commit `keys/`, VM disk images, or VM configuration.
- Current boot work is intended to be reversible and RAM-only; no iPadOS
  storage modification is part of the first-boot milestone.

## Relevant project files

- [`flake.nix`](../flake.nix): build systems, cross-compilation and dev shells.
- [`kernel/default.nix`](../kernel/default.nix): Apple kernel configuration.
- [`nixos/initramfs.nix`](../nixos/initramfs.nix): RAM-only userspace.
- [`boot/flash.sh`](../boot/flash.sh): boot orchestration.
- [`boot/load_linux.py`](../boot/load_linux.py): PongoOS USB uploader.
- [`boot/mkdtbpack.sh`](../boot/mkdtbpack.sh): DTB pack creation.
- [`research/`](../research/): hardware and driver research.

