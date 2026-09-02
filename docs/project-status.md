# iPad Linux Project Status

Status date: 2026-09-02  
Target: iPad Air 2 Wi‑Fi A1566, A8X/T7001, board J81/J81AP  
Repository: [mattonik/ipad-nixos](https://github.com/mattonik/ipad-nixos)
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

## Resolved PongoOS USB blocker (initial failed session)

In the initial session, PongoOS appeared on the iPad but macOS did not see the
expected PongoOS USB interface:

```text
Vendor/product: 05ac:4141
```

Both checks failed then:

```bash
irecovery -q
# ERROR: Unable to connect to device

python3 -c 'import usb.core; print(usb.core.find(idVendor=0x05ac, idProduct=0x4141))'
# None
```

`system_profiler SPUSBDataType` also showed no corresponding PongoOS device.

At that point the kernel uploader could not communicate with PongoOS. A later
direct-cable session resolved USB enumeration; the later payload attempt is
recorded below.

The remaining possibilities to investigate are:

- PongoOS USB gadget initialization on this iPad/cable/M1 macOS combination.
- Whether the checked-in PongoOS binary is compatible with this exact
  palera1n handoff.
- USB re-enumeration or driver behavior after the DFU-to-Pongo transition.
- Whether a known-good PongoOS build or PongoOS terminal utility sees the
  device when PyUSB does not.

This is a transport/handoff problem, not a kernel-build problem.

## Live PongoOS validation (2026-09-02)

This run proves PongoOS USB control on the target; it does **not** prove a
Linux boot. Every action was RAM-only and did not modify iPadOS storage.

### Confirmed

- Connecting the iPad directly to the M1 with a data-capable Lightning cable
  made PongoOS enumerate as USB vendor/product `05ac:4141`. A dock or hub was
  not sufficient in the failed session.
- PongoOS identifies itself as 2.6.1-742d92a0 and reports Apple A8X (T7001).
- PyUSB set the Pongo configuration and sent the harmless `help` and
  `bootargs` shell commands successfully.
- The checked-in `boot/Pongo.bin` matches the official PongoOS 2.6.1 release
  byte-for-byte. It is not a damaged local binary.

### Reliable Pongo USB check

Use the Darwin development shell. The fully qualified attribute matters:

~~~bash
nix develop '.#devShells.aarch64-darwin.default' --command python3 - <<'PY'
import usb.core

device = usb.core.find(idVendor=0x05ac, idProduct=0x4141)
assert device is not None, "PongoOS USB device not found"
device.set_configuration()
print(device.manufacturer, device.product)
PY
~~~

Expected output names PongoOS USB Device. This is the authority for whether
the host can upload a payload.

### Harmless shell smoke test

The Pongo command protocol uses a vendor control transfer. Run one short
command per fresh process; `help` is the preferred smoke test. The channel
reset mirrors upstream `pongoterm`.

~~~bash
nix develop '.#devShells.aarch64-darwin.default' --command python3 - <<'PY'
import time
import usb.core

device = usb.core.find(idVendor=0x05ac, idProduct=0x4141)
assert device is not None, "PongoOS USB device not found"
device.set_configuration()
device.ctrl_transfer(0x21, 4, 0xffff, 0, b"", timeout=5000)
device.ctrl_transfer(0x21, 3, 0, 0, b"help\n", timeout=5000)
time.sleep(0.2)
output = bytes(device.ctrl_transfer(0xa1, 1, 0, 0, 4096, timeout=5000))
assert b"pongoOS" in output
print(output.rstrip(b"\0").decode("utf-8", "replace"))
PY
~~~

Do not send `bootl`, `bootx`, `reset`, `crash`, `poke`, or a payload
from a diagnostic session.

### What failed and why it is not a Linux problem

- A visible Pongo logo did not mean that macOS had enumerated the device. In
  the failed session, IOKit had no Apple USB device, PyUSB returned `None`,
  and the uploader had no possible transport. Reconnecting directly resolved
  this without rebuilding the kernel or changing PongoOS.
- `irecovery -q` continued to report Unable to connect even after PyUSB
  controlled PongoOS successfully. Do not use that command as the PongoOS
  health check on this host.
- `nix develop .#aarch64-darwin` is not a valid selector for this flake. Use
  `'.#devShells.aarch64-darwin.default'`.
- A batched follow-up diagnostic hit a USB pipe error after the successful
  shell transaction. PongoOS stayed enumerated. Treat that as a host-control
  retry: reacquire the device, reset the command channel, and run one short
  command. Do not restart the whole exploit or assume the iPad has crashed.
- No Linux payload was uploaded in that diagnostic session. That was
  deliberate: the current initramfs and SSH path needed repair first.

### Next gate: an observable Linux handoff

1. Fix the init script so it creates `/proc`, `/sys`, `/dev`, `/etc`,
   and `/root` **before** mounting pseudo-filesystems. The built initramfs
   currently lacks these directories.
2. Build with a local public key explicitly supplied; this keeps ordinary
   builds key-free while allowing Dropbear key authentication:

~~~sh
IPAD_AUTHORIZED_KEYS="$PWD/keys/builder_ed25519.pub" \
  nix build --impure .#packages.x86_64-linux.initramfs -o result-initramfs
~~~

   Do not commit keys.
3. Rebuild the initramfs. Record its size and inspect it with
   `bsdtar -tf result-initramfs/initrd` before connecting the iPad.
4. Start a screen recording, then make one RAM-only upload from the Darwin
   development shell:

~~~bash
nix develop '.#devShells.aarch64-darwin.default' --command python3 \
  boot/load_linux.py \
  -k boot/Image.lzma \
  -d boot/dtbpack \
  -r result-initramfs/initrd \
  -c "console=tty0 loglevel=8 ignore_loglevel root=/dev/ram0"
~~~

The first success criterion is a Linux log or panic on the iPad display.
PongoOS can disconnect once Linux takes over USB. Do not expect USB Ethernet
or SSH: the J81 DTB currently has no USB device-controller node, so that is a
separate T7001 driver/device-tree port after a visible first boot.

### First RAM-only Linux handoff attempt — 2026-09-02

The initramfs repair and public-key injection were built and inspected before
the attempt:

- The output was 2,195,228 bytes. Its archived `/init` creates `/proc`,
  `/sys`, `/dev`, `/etc`, `/root`, `/tmp`, and `/run` before the first mount.
- `/root/.ssh/authorized_keys` was present as a link to the embedded Nix-store
  input; its payload checksum matched the supplied local *public* key.
- The kernel configuration includes `CONFIG_RD_ZSTD=y`, so it can unpack this
  Zstandard-compressed initramfs.

One upload was then made with `boot/load_linux.py`, using the J81 pack, the
10 MB LZMA kernel, and the initramfs above. The host's ramdisk, DTB, and
kernel transfer calls all completed. Sending `bootl` disconnected USB, which is expected:
PongoOS tears USB down before jumping to Linux. Within three seconds the iPad
enumerated as PongoOS (`05ac:4141`) again, not as Linux or Ethernet. No Linux
log, framebuffer output, or network interface was observed.

This does **not** exercise `/init`, Dropbear, or the Linux USB gadget. The
failure is earlier, in the PongoOS-to-Linux handoff. A subsequent read-only
Pongo shell command timed out despite USB enumeration; that repeats the known
host control-channel failure mode and is not evidence that a payload upload
failed. Do not repeat uploads until the bootloader path is instrumented.

A later host-side PyUSB `device.reset()` also timed out and left no DFU,
Recovery, or PongoOS USB device enumerated. It did not write iPad storage, but
it ended this RAM-only Pongo session. Do **not** use PyUSB device reset as a
Pongo recovery step; re-enter DFU and launch PongoOS through the established
palera1n command instead.

The exact PongoOS source matching `boot/Pongo.bin` is revision
`742d92a023d16c4cc9ebf9cb73b708bf92c52808`. Its Linux module states that it
is only supported on iPhone 7/A10, warns that non-A10 behaviour is undefined,
and uses an A10-specific fixed kernel entry address (`0x800080000`). The iPad
is T7001/A8X. This is the primary blocker, not an initramfs issue.

There is one safe DTB preflight to do when the Pongo shell is responsive: its
selector matches Apple `device-tree/target-type`, whereas the current pack
contains only `J81`. Build a temporary pack with both `J81` and `J81AP` keys
for the same `t7001-j81.dtb`, then record the Pongo selection message. That
eliminates a board-name mismatch without changing the kernel.

### Next technical step

1. Restore a responsive Pongo shell and capture its `dt` output or the DTB
   selection message; record the exact `target-type`.
2. Make a small, instrumented T7001 PongoOS fork from the pinned revision.
   It must report the selected DTB, initrd range, kernel entry address, and
   handoff result before USB teardown. Do not guess a replacement address or
   upload an uninstrumented binary.
3. Build that fork with a compatible PongoOS toolchain. The exact upstream
   source currently does not build with this host's Xcode 26: the old source
   trips stricter function-pointer checks and lacks the expected `va_start` /
   `va_end` declarations. This is a host-toolchain compatibility issue, not a
   reason to modify the iPad or retry the stock binary.
4. Retry one RAM-only payload only after the fork records a real jump. Capture
   the iPad display. Then, and only then, debug Linux early boot.

## Current state at a glance

| Stage | Status |
| --- | --- |
| Personal repository and remotes | ✅ Complete |
| Reproducible M1/Linux-builder workflow | ✅ Complete |
| Linux kernel build | ✅ Complete |
| Initramfs build and SSH-key preflight | ✅ Complete and archive-verified |
| J81 DTB generation and packaging | ✅ Complete |
| macOS gaster and development shell | ✅ Complete |
| DFU detection | ✅ Complete |
| checkm8 exploit | ✅ Complete |
| PongoOS upload | ✅ Complete |
| PongoOS visible on iPad | ✅ Complete |
| PongoOS USB interface `05ac:4141` | ✅ Verified with PyUSB control transfers |
| Current RAM-only Pongo session | ⚠️ Ended by a timed-out host USB reset; relaunch required |
| Linux payload upload | ✅ Transferred once; PongoOS re-enumerated after `bootl` |
| Linux kernel boot | ❌ Not achieved |
| Display/touch/Wi‑Fi/Bluetooth validation | ❌ Not started |
| Usable tethered Linux tablet | ❌ Future milestone |

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
