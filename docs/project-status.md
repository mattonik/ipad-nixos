# iPad Linux Project Status

Status date: 2026-09-04
Target: iPad Air 2 Wi‑Fi A1566, A8X/T7001, board J81/J81AP  
Repository: [mattonik/ipad-nixos](https://github.com/mattonik/ipad-nixos)
Upstream: [jacopone/ipad-nixos](https://github.com/jacopone/ipad-nixos)

**Resuming after a break? Start at "Playbook: next hardware session" near the
end of this file** (search for that heading) -- it has the exact launch
command, what to do for either outcome, and doesn't require reading the full
history above it.

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

### Guarded launch attempt after reconnect — 2026-09-02

The host independently confirmed DFU (`CPID 0x7001`, `PRODUCT iPad5,3`,
`MODEL j81ap`) and attempted to launch the locally built
`Pongo-t7001-diagnostic.bin`. The launch could not proceed: the `sudo` ticket
created in a separate terminal was not available to the Codex process, and the
macOS authorization fallback did not produce a USB device. Subsequent PyUSB
checks found none of DFU (`05ac:1227`), Recovery (`05ac:1281`), or PongoOS
(`05ac:4141`). No kernel, initrd, DTB, or `bootl` command was sent in this
attempt. This is an execution/USB-state failure, not evidence against the
diagnostic binary; the next run must start with one clean DFU launch and no
competing palera1n waiters.

### Clean DFU relaunch attempt — 2026-09-03

DFU was verified again for the target (`CPID 0x7001`, `iPad5,3`, `j81ap`).
The following sequence was tried and did not reach PongoOS:

1. `gaster pwn` succeeded as the logged-in user and reported `Now you can
   boot untrusted images.`
2. `irecovery -f boot/Pongo-t7001-diagnostic.bin` followed by `irecovery -c
   go` produced no transition; the device remained in DFU.
3. A subsequent standalone palera1n run reached `Checkmate!` but timed out
   waiting for download mode. The iPad then disappeared from USB before any
   PongoOS interface appeared.

No kernel, initrd, DTB, `linux_diag`, or `bootl` command was sent. The lesson
is to use one palera1n invocation from clean DFU and manually unplug/reconnect
the Lightning cable at its `Checkmate!` / `Device should now reconnect in
download mode` point; do not chain `gaster pwn` or the separate `irecovery`
loader first on this Mac.

### Stock PongoOS transport comparison — 2026-09-03

The stock `boot/Pongo.bin` was then launched through one clean palera1n
invocation from DFU. It reached PongoOS USB `05ac:4141`, and the harmless
`help` command confirmed `pongoOS 2.6.1-742d92a0` running on Apple A8X/T7001.
This proves the cable, exploit, download-mode transition, and Pongo USB
transport are healthy. The preceding custom-image attempt is therefore not a
valid binary regression test: it followed a separate `gaster pwn`/`irecovery`
sequence before palera1n. The next custom test must repeat the successful
single palera1n flow from fresh DFU, then run only `linux_diag`.

The exact PongoOS source matching `boot/Pongo.bin` is revision
`742d92a023d16c4cc9ebf9cb73b708bf92c52808`. Its Linux module states that it
is only supported on iPhone 7/A10, warns that non-A10 behaviour is undefined,
and uses an A10-specific fixed kernel entry address (`0x800080000`). The iPad
is T7001/A8X. A T7001-specific exit/handoff port is still required, but the
captured failure also exposed two earlier correctness defects below.

### Restored PongoOS USB after host timeout — 2026-09-03

A later stock-Pongo run again reached `Checkmate!` and palera1n timed out
waiting for download mode. The iPad nevertheless reached the Pongo logo. On
that screen, unplugging and reconnecting the Lightning cable caused macOS to
enumerate `05ac:4141`. A control-channel `help` query then returned:

```text
pongoOS 2.6.1-742d92a0
Built with: Clang 14.0.0 (clang-1400.0.29.202)
Running on: Apple A8X (T7001)
```

Consequently, a palera1n download-mode timeout alone does not prove that
PongoOS failed to start on this host. If the Pongo logo appears, leave the
iPad in that RAM-only session and replug the cable before abandoning the run.
Do not upload a Linux payload to stock PongoOS; use the guarded diagnostic
binary below after the next clean DFU relaunch.

### PongoOS compiler isolation — 2026-09-03

The checked-in stock image reports Apple Clang 14.0.0
(`clang-1400.0.29.202`). The host reports Apple Clang 21.0.0, while the
upstream CI for this revision builds with `clang-10`. A
clean source checkout was built with only the two compatibility edits required
by Clang 21 (`stdarg.h` in `task.c` and the `ttb_alloc` function-pointer cast
in `mm.c`). That image reached palera1n's `Booting PongoOS...` stage but did
not re-enumerate PongoOS USB; it must not be used for the T7001 diagnostic.

Removing LTO from both the root and Newlib makefiles produced a second clean
image (`254056` bytes, SHA-256
`8413d44901eeb591765b60e152ad4ea632827e8b71075f2bccb58884f897eb93`). It
also completed the build but the launch attempt did not reach PongoOS USB;
the exploit timed out waiting for download mode. This run is inconclusive as
an image comparison because the device disappeared before the payload could
be observed. The useful conclusion is that the repository's supported build
toolchain is old Clang (CI uses clang-10), not the current Apple Clang 21.

Nix Clang 11.1.0 with the macOS linker built a complete guarded diagnostic
image (`254040` bytes, SHA-256
`62be4d4bf2fe870b9b3f7054965fb6905c59d7848add991201e72de7b75b15f0`), but a
fresh, unmodified baseline built with that same compiler (SHA-256
`ee83f490dfdc58ae198066a1d257c6e0900979e6546f120790cdcc3cd5fc97db`) showed
only a dark screen and then required DFU recovery. This rules out the patch as
the cause and rules out Nix Clang 11 as a PongoOS compiler for this device.
Immediately afterward, the host found no Apple USB device (`05ac:*`), so there
was no live Pongo session to query or recover. Do not rebuild or launch that
image again.

Homebrew LLVM 14.0.6 can compile an unmodified baseline (SHA-256
`35ff111ddb62722db00bfedf0a7adb85b1ea109d963828b4328917321558b275`), but it
is upstream LLVM rather than Apple's Clang and has not been launched. It is
not evidence of a usable compiler and is not a reason to consume another DFU
cycle.

The only known-good reference is the checked-in stock Pongo image, built with
Apple Clang 14.0.0 (`clang-1400.0.29.202`). Apple's official Command Line Tools
for Xcode 14.2 download requires an authenticated Apple Developer session; the
unauthenticated URL redirects to Apple ID sign-in. The official image downloaded
on this host was 704,636,731 bytes with SHA-256
`7ed7b1fb951461f911697d519ce27cb45932f256aa2a52a562619bb6bec1037f`.
`hdiutil verify` succeeded and its `Command Line Tools.pkg` reports `signed
Apple Software` through `pkgutil --check-signature`.

`boot/extract-clt14.sh` verifies that image and extracts its executable payload
without installing or replacing the active Xcode 21 toolchain. It validated the
exact compiler and produced the guarded image from a fresh checkout: 254,040
bytes, SHA-256
`b345dc3cba9e6b99f5765f1858d42f4158d6d721afec153498745ac3c706b222`.

That first image did **not** display PongoOS. It used the exact Clang but the
active Xcode 21 linker (`ld-1267`), so it was not a complete Xcode 14.2
toolchain test. palera1n reached `Checkmate!` then its usual 20-second M1
download-mode timeout; the iPad showed no Pongo logo and reconnecting the cable
restarted iPadOS. No `linux_diag`, payload upload, or Linux jump occurred. The
extracted image also provides `ld64-820.1` with LLVM 14 LTO support. The
builder and extractor now require both exact components; rebuild from a fresh
checkout before the next device launch. Do not retry the `b345dc3c...` image.

A clean rebuild with that matched compiler/linker pair completed successfully:
254,040 bytes, SHA-256
`1f8021cd7605c950f807ba80a3409d169f0c2731fb179fa0da4d4d02bfe60f9e`.
The Newlib configure and Pongo link commands both named the extracted tools.
This is the only custom Pongo image approved for the next RAM-only
`linux_diag` attempt; it has not yet run on the device.

That run reached a Pongo logo after the documented Lightning reconnect, and
`help` confirmed the custom `linux_diag` command over USB. The kernel, J81 DTB
pack, and initramfs uploaded successfully. `linux_diag` selected J81, then
reported `Decoded Linux Image size is invalid: 43384832.` PongoOS remained
running and no `bootl` or Linux jump was sent.

This uncovered a guard bug, not a malformed kernel: the 42,404,352-byte
decompressed `Image` has an arm64 header layout size of 43,384,832 bytes. The
extra 980,480 bytes are BSS layout space, so a valid header layout size must be
at least the decompressed file size, not at most it. The guard now enforces
`decompressed_size <= layout_size <= 64 MiB`; `boot/test_t7001_pongo_diagnostic.py`
checks the real artifact and that bound. Rebuild the diagnostic after this
patch before repeating `linux_diag`.

The corrected matched-toolchain rebuild completed at 254,040 bytes, SHA-256
`2b9405eec0fcfd6d7be5e3659f70b1bab5584fa959307da1ed2c6dc66eaf3574`.
The live Pongo session still contains the earlier safe-but-rejecting image, so
it must not be reused for a second diagnostic. Re-enter DFU, launch only this
new image, reconnect the cable at the Pongo logo, then run `linux_diag` again.

That corrected run succeeded. After the second Lightning reconnect, PyUSB
confirmed PongoOS and `linux_diag`; the kernel, J81 DTB pack, and initramfs
uploaded again. The first read returned only the early J81 selection because
LZMA decompression was still in progress. A read-only follow-up returned:

```text
initrd @ 0x877294000-0x8774ac868
[t7001] soc=7001 phys=0x800c00000 size=7c4de000 iBoot-entry=0x802b35490
[t7001] image=43384832 stage=0x4774b4000/0x8774b4000 fdt=0xe002aa0a0 (262144 bytes)
[t7001] initrd=0x477294000/0x877294000 (2197607 bytes)
[t7001] candidate-entry=0x800080000; diagnostic only, no jump attempted.
```

This is the first verified T7001 Linux payload measurement. It proves the
patched staging, DTB overlay, initramfs placement, and no-jump guard. It does
not prove a Linux entry address, cache state, exception level, or a kernel
boot. `boot/load_linux.py` now polls diagnostic output for up to 10 seconds,
so the delayed success marker is captured in one safe invocation.

### ARM64 handoff-candidate diagnostic — verified on T7001 (2026-09-03)

The first measurement also showed why it was not a Linux handoff candidate:
the Image stage at 0x8774b4000 was not 2 MiB aligned and the expanded DTB was
heap-backed at 0xe002aa0a0, which has no single physical address.

The current diagnostic fixes only those two staging defects. It reserves an
extra 2 MiB, places the Image so stage_phys minus text_offset is 2 MiB aligned,
and copies the final DTB into contiguous RAM. It then reports the physical DTB
to use in x0, with x1=x2=x3=0, the current exception level, and the candidate
Image address. It still frees those candidate buffers and prints the no-jump
marker; it never changes the boot flag, disables the MMU, or exits PongoOS.

The production Image was checked as text_offset=0, file size 42,404,352 bytes,
and layout size 43,384,832 bytes. The rebuilt guarded binary is 254,040 bytes
with SHA-256 0dcd438bc1f944fc5c9e34ab75982a9a8835529010302292141357ee63d3a489.
The diagnostic checks and uploader no-jump test pass, and the patch applies
cleanly to PongoOS 742d92a. The new image was then launched on the iPad and
the complete payload transaction succeeded:

~~~text
[t7001] soc=7001 phys=0x800c00000 size=7c4de000 iBoot-entry=0x802b35490
[t7001] image=43384832 stage=0x477400000/0x877400000 text-offset=0 base=0x877400000
[t7001] fdt=0x47c1f4000/0x87c1f4000 (262144 bytes), x0=0x87c1f4000 x1=x2=x3=0 EL1
[t7001] initrd=0x477098000/0x877098000 (2197607 bytes)
[t7001] candidate-entry=0x877400000; diagnostic only, no jump attempted.
~~~

This is the first verified T7001 handoff-candidate measurement. The image,
DTB, initramfs, and register values are real device values; the command still
does not disable the MMU, clean caches, quiesce DMA, or transfer control.

### Step 1: explicit T7001 transfer path — build verified, not device-tested (2026-09-03)

The next small change preserves the prepared Image and DTB through PongoOS
teardown. For T7001, linux_boot now skips the A10 copy to 0x800080000; after
PongoOS has torn down USB/interrupts, cleaned caches, and disabled the MMU,
the entry path calls the existing raw jump helper with the retained physical
Image and DTB addresses. That helper sets x0 to the DTB and clears x1 through
x3.

This path is intentionally separate from bootl. The new linux_t7001 command
is accepted only on socnum 0x7001, while bootl remains rejected on this chip.
boot/load_linux.py exposes it only through the explicit --t7001-handoff flag.
The rebuilt image is 254,040 bytes with SHA-256
a5c67769e3bdbc48452e59d723dbbafd6ca58f090c72a3367be0f3dcba888149.
The patch applies to the pinned PongoOS revision and builds with the verified
Xcode 14.2 toolchain; host-side tests pass.

No handoff was attempted in this step. The current iPad session contains the
previous diagnostic image. The next hardware step is to launch this new
binary, rerun linux_diag, and inspect its preserved physical addresses before
choosing whether to invoke --t7001-handoff.

The intended contract follows the upstream [AArch64 Linux boot
protocol](https://docs.kernel.org/arch/arm64/booting.html): a DTB physical
address in x0; zero in x1 through x3; an Image placed at its declared offset
from a 2 MiB-aligned base; and, before any future exit, quiesced DMA, masked
interrupts, non-secure EL1/EL2 with MMU off, and the Image cleaned to the point
of coherency. The diagnostic measures the address and register parts only.
The exit/cache/exception transition is a separate, still unimplemented T7001
port.

### Step 2: first T7001 Linux handoff attempt — silent hang, no panic (2026-09-03)

The Step 1 build/patch pairing was stale: `boot/Pongo-t7001-diagnostic.bin` on
disk predated the prepared-state guard (`gLinuxPrepared`, added to
`boot/pongo-t7001.patch` to stop a jump on failed preparation) that was the
point of that change. Rebuilt from a fresh pinned checkout against the current
patch: 254,032 bytes, SHA-256
`d2c6d8a1229a64d8a83dcd867489cd01ee141c648639896fdcb81ed218fc953b`. This
supersedes the `a5c67769...` build recorded above. `boot/test_t7001_pongo_diagnostic.py`
and `boot/test_load_linux_diagnostic.py` both pass against it.

Launched via the documented palera1n flow (fresh DFU, direct-to-Mac Lightning
reconnect at the Pongo logo). A `linux_diag` re-check reproduced the same
measured contract as the earlier verified diagnostic — Image staged at
`0x877400000`, DTB at `0x87c1f4000` with `x0` set and `x1=x2=x3=0`, `EL1` —
confirming the guarded build stages identically to the prior candidate.

`--t7001-handoff` was then sent once. PongoOS accepted `linux_t7001`, printed
its unconditional legacy `linux_prep_boot` banner (including the fixed
`0x800080000` string, which is a leftover print and not the real T7001
target), then `Booting Linux...`, and produced no further output. USB
disconnected, consistent with PongoOS's pre-jump teardown. The iPad screen
stayed on that frozen text and stopped responding to anything but a hard
restart; the restart is safe and expected — this remains RAM-only and does
not touch iPadOS storage.

No panic or synchronous exception was printed this time, unlike the earlier
stock-Pongo attempt against an A10 entry address. This does **not** confirm
Linux executed: the J81 DTB has no verified UART, framebuffer-console, or
USB-console path, so a successful jump into a live but silent kernel would
currently look identical to a hang. It does rule out an immediate
PongoOS-side fault at the jump site, and narrows the open question to
whether control reached the kernel at all, and if so why there is no console
output.

The next diagnostic step is to get a signal that does not depend on the DTB
having a working console before repeating this — for example an earlycon
path proven independently, or a PongoOS-side heartbeat/marker written to a
fixed physical address that can be read back after a forced restart. Do not
repeat `--t7001-handoff` again without first adding that observability; a
second blind attempt would not distinguish "booted silently" from "crashed
silently" any better than this one did.

The current hardware blocker was then isolated further: a fresh DFU run of
the proven stock `boot/Pongo.bin` also reached `Checkmate!` but timed out
waiting for download mode. Therefore this is not a Pongo image, kernel,
initramfs, touch, or Wi-Fi failure. Palera1n documents this as an Apple
Silicon USB-C limitation; use a USB-A Lightning cable through a USB-A hub (or
another host) for the next test. Direct USB-C may require a precisely timed
unplug/replug after checkm8 and is presently unreliable on this Mac.

The bundled palera1n was v2.0.2. The current official arm64 macOS release,
v2.4, was downloaded and verified (SHA-256
`950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9`). It was
started with the stock Pongo image, but the host saw no DFU device, so no
exploit or image comparison occurred. Do not keep restarting the iPad while
macOS reports no USB device; first restore USB enumeration or move the DFU
session to another host.

### Captured PongoOS failure and ruled-out work (2026-09-02)

The supplied iPad screen capture records the first payload attempt directly:

- PongoOS selected `J81` and printed `Found device tree for J81 (26581
  bytes).` The target-type lookup therefore works; do **not** add a duplicate
  `J81AP` pack entry as a speculative fix.
- It printed the supplied command line and initrd range, then
  `Failed to delete bootargs`. The generated J81 DTB has `/chosen` but no
  pre-existing `bootargs`; upstream treats that normal condition as a failure
  and then continues with a malformed overlay.
- It reached `Assuming decompressed kernel`, followed by a synchronous
  exception and double panic before Linux output. The kernel is a valid
  42,404,352-byte Image, while the upstream code allocates its staging area
  from the 10,812,698-byte compressed input but allows LZMA to write up to
  256 MiB. This is a definite out-of-bounds write before any possible Linux
  handoff.

The iPad was no longer USB-enumerated after the double panic. Reconnecting a
cable does not revive that RAM-only session: re-enter DFU and relaunch PongoOS
for the next test. Do not send another stock `bootl` payload.

### Guarded T7001 PongoOS diagnostic

`boot/pongo-t7001.patch` is a small patch against exactly the pinned upstream
revision. It is deliberately a **diagnostic**, not a Linux handoff port:

- sizes the LZMA staging area for the uncompressed Image (bounded at 64 MiB),
  validates the Image header, and refuses oversize payloads;
- selects the DTB into a separate buffer, expands it out of place, and sets
  `/chosen/bootargs` without requiring a prior property;
- adds `linux_diag`, which applies the DTB/initrd overlay and prints the
  contiguous physical DTB and prints the Linux register contract without
  jumping; and
- rejects `bootl` on `socnum == 0x7001`, so the diagnostic binary cannot
  accidentally attempt the known-invalid A10 transfer on this iPad.

Build it from a fresh official checkout. The compatibility edits in the patch
do not make Apple Clang 21 valid, and the dark-screen baseline proves Nix
Clang 11 is not valid either. The builder deliberately accepts only the exact
Apple Clang version reported by the stock image.

~~~bash
./boot/extract-clt14.sh \
  "$HOME/Downloads/Command_Line_Tools_for_Xcode_14.2.dmg" /tmp/CLT14
git clone --recurse-submodules https://github.com/checkra1n/PongoOS.git /tmp/PongoOS-t7001
git -C /tmp/PongoOS-t7001 checkout 742d92a023d16c4cc9ebf9cb73b708bf92c52808
PONGO_CC=/tmp/CLT14/Library/Developer/CommandLineTools/usr/bin/clang \
PONGO_LD=/tmp/CLT14/Library/Developer/CommandLineTools/usr/bin/ld \
  ./boot/build-pongo-t7001-diagnostic.sh /tmp/PongoOS-t7001
~~~

The build script rejects checkouts with existing Pongo or Newlib output. That
matters: a first exact-compiler build reused a previously generated Newlib
archive and failed to link because it contained objects from active Xcode 21.
The guard forces the compiler choice through both Pongo and Newlib.

After physically re-entering DFU, launch the generated ignored local binary:

~~~bash
sudo /tmp/palera1n-arm64 --pongo-shell \
  --override-pongo "$PWD/boot/Pongo-t7001-diagnostic.bin" --debug-logging
~~~

Then run the usual uploader with `--diagnostic`:

~~~bash
nix develop '.#devShells.aarch64-darwin.default' --command python3 \
  boot/load_linux.py --diagnostic \
  -k boot/Image.lzma -d boot/dtbpack -r result-initramfs/initrd \
  -c "console=tty0 loglevel=8 ignore_loglevel root=/dev/ram0"
~~~

The required success marker is `diagnostic only, no jump attempted.` together
with the selected `J81`, 2 MiB-aligned Image base, physical DTB, `x0`, and
initrd ranges. The uploader exits non-zero unless it sees that marker. This
test is RAM-only and leaves PongoOS running. It is the gate for studying
T7001's real exception/cache/EL state; the measured candidate entry is not an
authorization to jump to Linux.

### Step 3: pre-jump framebuffer marker checkpoint — build verified, not device-tested (2026-09-03)

Step 2 left an open question that another blind `--t7001-handoff` cannot
answer: whether the CPU ever executed a single instruction of freshly
written physical code after PongoOS's teardown, independent of the J81
DTB's unverified console/UART/USB path. `src/boot/t7001_boot_marker.S`
adds a small position-independent stub for exactly that: it runs between
`jump_to_image`'s teardown and the real kernel entry, writes a solid
white 8-row band directly to the physical framebuffer
(`gBootArgs->Video.v_baseAddr` — the same raw physical pointer
`pongo_entry` itself assigns to `gFramebuffer` at this exact phase for
every boot path, so this introduces no new hardware assumption), then
branches to the real kernel entry address with `x0` (DTB) preserved and
`x1=x2=x3=0` as the AArch64 boot protocol requires.

`linux_prep_boot()` now stages this stub into its own small allocation,
patches the framebuffer address, marker color, word count, and real
kernel entry address into its data area, and `cache_clean()`s it —
`gLinuxPrepared` is only set `true` after that clean succeeds. The T7001
jump in `entry.c` now targets this marker stub (`gLinuxMarkerStage`)
instead of jumping into the kernel Image directly.

While tracing this, the marker's own cache-clean turned up a related gap:
`linux_prep_boot()` copies the kernel Image and DTB into their staging
buffers but never calls `cache_clean()` on either before the jump, unlike
the framebuffer driver elsewhere in this codebase, which treats that
clean as mandatory before the display controller can see written pixels.
That is a plausible contributor to Step 2's silent hang on its own,
independent of the console gap. It has deliberately **not** been fixed
here — fixing it changes what a positive/negative marker result would
mean, so it stays a separate, explicit next step (see below) rather than
being bundled into this diagnostic.

Interpreting the next hardware run: if the framebuffer band appears and
the boot still hangs afterward, the teardown/jump mechanism is proven to
reach and execute freshly staged physical code, which narrows the failure
to the still-unclean Image/DTB or the kernel itself. If the band never
appears, the failure is at or before the marker stub — in `jump_to_image`
itself, or in how it was staged.

Built from a fresh pinned checkout with the matched Xcode 14.2
Clang/ld64-820.1 toolchain: 254,032 bytes, SHA-256
`000f21df79bbb24b74ac57f1b9a697e035fe6081caf705fa88cda40c8c235c8f`.
`boot/test_t7001_pongo_diagnostic.py`, `boot/test_load_linux_diagnostic.py`,
and the new `boot/test_t7001_boot_marker.py` (structural checks: stub
symbols exist, the asm/C data offsets agree, `gLinuxPrepared` is only set
after the marker is staged and cleaned, and the jump targets the marker
stub rather than the kernel directly) all pass.

### First marker run — inconclusive (2026-09-03)

Launched this build, re-confirmed the same `linux_diag` measurement as
the prior verified run (Image at `0x877400000`, DTB at `0x87c1f4000`,
`x0` set, `EL1`), then sent `--t7001-handoff` once with the device
watched throughout.

The observer reported a brief blink: an approximately 80px-tall
red/black band across the screen width, in the bottom third of the
screen. That does not match what the stub was coded to draw — a solid
white, 8-pixel-tall band at the top-left of the framebuffer (`v_baseAddr`
onward), roughly 10x smaller and a different color and position. This is
recorded as **inconclusive, not a confirmed marker sighting**: it may be
an unrelated display artifact from the teardown/reconnect rather than
evidence the stub executed. The screen returned to the same frozen
PongoOS console text as the Step 2 hang, and the device stopped
responding to anything but a hard restart, exactly as before.

Two design gaps likely explain why this couldn't be read confidently
even if it was the stub: the marker is tiny (8 physical rows) and
transient (it draws once, then the code continues straight into the
kernel jump, so any distinguishing display state it left behind is only
as stable as whatever happens next). Both are being fixed before the
next attempt — see below.

### Marker v2: full-screen fill, spin-forever isolation (2026-09-03)

Also worth noting for its own sake: the observer confirmed the default
PongoOS screen is light/white, not dark, which independently explains
why the first marker (solid white, `0xffffffff`) could have been
invisible even if the stub ran correctly — it's the wrong lesson to draw
from the ambiguous blink report alone, but it is a real bug in that
version regardless.

`t7001_boot_marker.S` and its staging in `linux_prep_boot()` were revised:

- The fill now covers the entire framebuffer
  (`gBootArgs->Video.v_height * gBootArgs->Video.v_rowBytes`), not an
  8-row band.
- The color is now opaque black, `0xff000000` in the DTB's declared
  `a8b8g8r8` layout — chosen to read as black (or at minimum some
  strongly saturated, obviously-not-background color if the channel
  assumption is wrong) regardless of whether alpha is honored, and to
  contrast with the confirmed-light default screen.
- A new `continue_flag` field (`marker_data+24`) controls what happens
  after the fill: zero spins forever in place; nonzero branches onward to
  `gLinuxStage`, exactly like the first version always did. **This build
  hardcodes it to zero.** The fill is now the entire, isolated test: does
  execution reach and survive in freshly staged physical code, with a
  stable, indefinitely-photographable end state that cannot be confused
  with anything the kernel jump itself might do. Continuing into the
  kernel jump is deliberately deferred to a later build, once a fill is
  confirmed to actually hold.

Built from a fresh pinned checkout with the same matched toolchain:
254,032 bytes, SHA-256
`32e24d58d0970dcd0476b00935e6ae43d0aa83014334c8e83283689e2ce83f23`.
All three test scripts pass, including `boot/test_t7001_boot_marker.py`
updated for the new offsets, color, and spin-forever default.

### v2 hardware run — inconclusive, likely unrelated artifact (2026-09-03)

Launched this build, re-confirmed the same `linux_diag` measurement as
every prior verified run, then sent `--t7001-handoff` once. The device
was recorded on video (11.5s) for the entire attempt and checked
frame-by-frame afterward: the screen shows the normal PongoOS
logo/console the whole time. No black fill ever appears. One frame
(around the 6.5s mark) shows a brief reddish tint over the still-intact
logo, which the observer also saw directly (not a camera artifact). The
device then stopped responding to USB control transfers, though it
remained visible as a USB device to macOS rather than fully
disconnecting — a different failure signature than the v1/Step 2 runs.

This reddish blink is the same category of artifact v1 reported (there,
an ~80px red/black band in the bottom third), despite v1 and v2 being completely
different marker designs — different size, color, and hold behavior. If
either marker had actually executed, the visual signature should have
tracked the design change; it didn't. The parsimonious read is that this
blink is **not** the marker's output at all, but something intrinsic to
PongoOS's own teardown sequence that happens on every `linux_t7001`
attempt regardless of what code runs afterward (a display clock/power
transition, MMU/cache teardown side effect, etc.). Neither run has
produced confirmed evidence that execution reaches the marker stub.

### Marker v3: continuous two-color strobe (2026-09-03)

Two possible explanations remain for why a correctly-executing marker
still wouldn't produce visible output: the display could be
double-buffered, so a single write can land in a buffer that's never
actually scanned out; and a single write is inherently hard to
distinguish from a one-off artifact like the reddish blink. v3 addresses
both by replacing the one-shot fill with an infinite loop that fills the
whole framebuffer solid black, holds (~0.3-1s busy-wait), fills it opaque
bright green (`0xff00ff00`, chosen to survive an unknown a8b8g8r8
channel-order assumption the same way opaque black does), holds, and
repeats forever. It never continues to the kernel in this build — see
`t7001_boot_marker.S` for the full v1/v2/v3 history recorded alongside
the code. A repeating write is far more likely to eventually hit the
active scanout buffer than a single one, and a blinking two-color pattern
cannot be confused with a brief, one-off artifact the way a static fill
could.

If the strobe is visible at all, execution reached and is still running
in freshly staged physical code — full stop, regardless of the reddish
blink's cause. If it is not visible, the failure is at or before this
stub, in `jump_to_image`'s own teardown/jump path, and the reddish blink
becomes the more interesting thing to chase next.

Built from a fresh pinned checkout with the same matched toolchain:
254,032 bytes, SHA-256
`48c2b288ba1aa4e24e56906686713c52b2d86122c21c4bde8790c748e2c75d60`.
All tests pass, including `boot/test_t7001_boot_marker.py` updated for
the strobe design.

### v3 hardware run — negative, plus a new lead (2026-09-03)

Launched this build, re-confirmed the same `linux_diag` measurement as
every prior verified run, then sent `--t7001-handoff` once. This run was
recorded on video for its full 12.4s duration and checked frame-by-frame
at 4fps: the screen shows the normal PongoOS logo/console the entire
time, with no black or green fill visible even once — a clean negative
result for the strobe itself. The device again stopped responding to USB
control transfers while remaining visible as a USB device to macOS,
matching the v2 signature rather than the v1/Step 2 clean-disconnect
signature.

Separately, the observer reported a brief flash right after the command
was sent, too fast to land on any 4fps-sampled frame. Asked directly, they
described it as reddish and a fraction of a second — matching v1's and
v2's reports almost exactly, despite v1, v2, and v3 being three
unrelated marker designs (different size, color, and hold behavior each
time). If any of the three markers had actually executed, the visual
signature should have tracked the design change; it never did. The
conclusion recorded here is that this reddish flash is **not** any
version of this stub's output, and is most likely intrinsic to PongoOS's
own teardown sequence on every `linux_t7001` attempt, independent of what
code runs afterward. No version of the marker has produced confirmed
evidence that execution reaches it.

### The jump_to_image tramp=0 gap (2026-09-03)

Given three marker designs in a row showed no confirmed sign of
executing, the more promising lead turned out to be upstream of the
marker entirely. `jump_to_image()` (`src/boot/jump_to_image.S`) takes an
`image`, `args`, and `tramp` argument; when `tramp` is nonzero and the
live hardware needs it (checked at runtime via `id_aa64pfr0_el1` and a
`need_to_release_L3_SRAM` flag set during the checkm8 exploit's own
bootloader patching, not hardcoded per chip), it releases L2/L3 cache
that iBoot leaves locked down as SRAM before jumping. When `tramp` is
zero, none of that runs — the function takes an unconditional "raw" path
straight to the jump. Its own source comment on that path: *"If we were
passed no tramp page, then oh well. You better not be booting any kernel
here."*

Every `jump_to_image` call this patch added (the diagnostic-only
measurement path, and the real T7001 handoff through v3) passed `tramp=0`
— exactly the case that comment warns against. The one call elsewhere in
this codebase that actually boots a full OS on the non-RAW path,
`exit_to_el1_image()` at the end of `pongo_entry()`, always passes a real
computed trampoline address, never zero. If this device's SRAM is in fact
locked at this point (plausible: the release mechanism is generic to the
checkm8 exploit chain, not A10-specific), skipping it could leave cache
state that makes any subsequent physical code — our marker, the kernel
Image, or both — behave unpredictably, independent of what that code
actually contains. This is a strong candidate for explaining why nothing
tried so far, marker or otherwise, has produced a confirmed positive
signal.

### Marker v4: real tramp buffer, corrected + robust strobe (2026-09-03)

Two fixes landed together. `linux_prep_boot()` now allocates and
cache-cleans a second small physical scratch page and passes its physical
address as `jump_to_image`'s `tramp` argument instead of `0`, so the
SRAM-release path can actually run if the live hardware state calls for
it — the existing runtime checks decide whether it's needed, this just
stops forcibly skipping that decision.

The strobe itself also gained a `repeat_count` field: each color phase
now re-fills the whole screen 15 times (~50M busy-wait iterations apart)
before switching, rather than filling once and delaying once. This makes
the total hold time per color resistant to a wrong per-iteration cycle
guess (relevant given v3's flash may have been real but far shorter than
intended), and re-asserts the color repeatedly rather than once, in case
anything else is periodically touching the framebuffer.

Fixing this in the same pass caught a real bug worth recording: the
`t7001_boot_marker.S` data section grew from 24 to 32 bytes to fit the
new field, but the first draft of the C-side patch code still computed
the data pointer as `marker_size - 24` and never set the new field at
all — which would have left `repeat_count` as zero, underflowed to
`0xFFFFFFFF` on the first decrement, and turned each color phase into
roughly four billion re-fills (an effectively permanent hang on the first
color, never reaching the second). Caught before building by re-reading
the staged C code against the revised assembly layout rather than trusting
the earlier edit; both are now fixed and covered by
`boot/test_t7001_boot_marker.py`'s offset and ordering assertions.

Built from a fresh pinned checkout: 254,032 bytes, SHA-256
`0d89ff9b7384505ba23bc75df97de56aaf5cdc2e712a6030fef603f7ff147dc2`. All
tests pass, including `boot/test_t7001_boot_marker.py` updated for the
tramp buffer and repeat count.

### v4 hardware run — tramp fix inconclusive; reddish band explained (2026-09-03)

Launched this build, re-confirmed the same `linux_diag` measurement, then
sent `--t7001-handoff` once, recorded in slow motion (30fps). The strobe
was never visible. The reddish artifact was, though, and this time
clearly enough to place it: a pink/red band, full width, confined to the
very bottom edge of the screen, lasting about two frames (~0.13s at
15fps-sampled review) before vanishing back to normal console text — and
the console kept printing more lines shortly after, so PongoOS was never
actually stuck at that point.

That band's position and behavior turned out to have a mundane
explanation, unrelated to anything in this patch. `linux_prep_boot()`
(unmodified code, present before this session's changes) directly pokes
real display-controller hardware registers just before the "iPhone 7
only" print:

```c
volatile uint32_t *disp = ((uint32_t *)(dt_get_u32_prop("disp0", "reg") + gIOBase));
*pixfmt0 = (*pixfmt0 & 0xF00FFFFFu) | 0x05200000u;
*colormatrix_bypass = 0;
*colormatrix_mul_31 = 4095;
*colormatrix_mul_32 = 4095;
*colormatrix_mul_33 = 4095;
```

This reconfigures the display's pixel format and color-matrix pipeline
while the console is still actively rendering through it — a textbook
cause of a brief, fixed-color, fixed-timing visual glitch. It explains
every observed property: why it's always reddish (a specific hardware
transition, not our color choice), why it never depended on any marker
design across v1-v4 (this code runs before our marker/tramp staging even
starts), why it only ever happened during real `linux_t7001` attempts
and never during `linux_diag`-only runs (`linux_diagnostics()` doesn't
call this code path), and why PongoOS kept running afterward (it's
cosmetic, not a fault). This band is not evidence for or against whether
our marker executes, in either direction, and is not planned to be
touched.

The open question is unchanged: still no confirmed evidence execution
reaches the marker after four hardware attempts.

### t7001_color_test: an intentionally boring, safe sanity check (2026-09-03)

Every attempt so far has conflated two untested things: whether the
marker's framebuffer-writing logic is correct, and whether execution
survives `jump_to_image`'s teardown. If either fails, the symptom looks
identical (nothing visible, PongoOS unresponsive afterward), so failures
in one can't be told apart from failures in the other.

Added `t7001_color_test`, a plain PongoOS shell command with no
connection to the boot-flag/teardown/jump path at all -- it cannot hang,
because nothing about it is irreversible. It reuses `screen_fill()`
(the exact primitive `fbclear`/`fbinvert` already use safely, via the
already-working virtual framebuffer mapping) to fill the screen with the
marker's exact colors three times, then restores the console with
`screen_clear_all()`:

```c
void t7001_color_test() {
    for (int i = 0; i < 3; i++) {
        screen_fill(0xff000000u); // opaque black, a8b8g8r8
        sleep(1);
        screen_fill(0xff00ff00u); // opaque bright green, a8b8g8r8
        sleep(1);
    }
    screen_clear_all();
    puts("t7001 color test done");
}
```

If this doesn't look like solid black then solid bright green, the
a8b8g8r8 color-channel assumption baked into `t7001_boot_marker.S` is
simply wrong, independent of anything about the jump/teardown mechanism.
If it does look right, that assumption is eliminated as a variable, and
whatever the next real handoff attempt shows is more clearly about
`jump_to_image` and the teardown, not about color math.

Built from a fresh pinned checkout: 254,032 bytes, SHA-256
`ff27b812444842dffc9007927a6c106c8c7eaf92a1f2b32b8c633011e51d7e8d`. All
tests pass. **Not yet run on hardware.**

### Next technical step

1. Launch this build and run `t7001_color_test` over USB (a plain shell
   command, not through `load_linux.py` -- no kernel/dtb/initrd upload
   needed first). Confirm it shows solid black, then solid bright green,
   three times, then restores the console -- and that PongoOS stays fully
   responsive to further commands throughout and after.
2. If the colors look wrong (wrong hue, or nothing changes), the
   a8b8g8r8 assumption in `t7001_boot_marker.S` is the bug; fix that
   before touching the jump path again.
3. If the colors look right, run `linux_diag` to confirm the same staged
   addresses as every prior verified run, then send `--t7001-handoff`
   once with the device watched/recorded, per the v4 build above (tramp
   fix + strobe). A confirmed-correct color test removes one whole
   category of explanation for why the strobe hasn't been seen yet.
4. Only after a visible Linux log, resume the console, touch, and Wi-Fi work
   already recorded below. The current driver approval gate remains in force.

### v5 hardware run — colors confirmed correct; real handoff still fails (2026-09-03)

`t7001_color_test` was launched and run over plain USB shell commands (no
`load_linux.py`, no kernel/dtb/initrd upload). The observer confirmed
clear black/green switches, then a leftover green rectangle at the top of
the screen — exactly as expected, since `screen_clear_all()` deliberately
restores everything except the banner region and our fill (correctly)
covered the banner too. PongoOS answered `help` immediately afterward
with no issues. This is an unambiguous positive result: the marker's
exact `0xff000000`/`0xff00ff00` a8b8g8r8 color constants render as solid
black and solid bright green on this hardware. That whole category of
explanation is now closed off.

`linux_diag` was re-run on the same live session (same measured
addresses as every prior verified run), then `--t7001-handoff` was sent.
No strobe was visible anywhere across a 12.9s recording -- only the
pre-existing leftover green banner strip from the color test, static the
whole time, and a brief red flash matching the already-explained
`pixfmt`/color-matrix artifact. The device again went to the same
"enumerated but unresponsive" state as the v2-v4 attempts. So: with
validated colors and the tramp fix both in place, the real handoff still
produces no confirmed evidence of reaching the marker.

### t7001_sram_check: verifying the tramp fix actually changed anything (2026-09-03)

The tramp fix (giving `jump_to_image` a real scratch page instead of `0`)
only changes behavior if the live hardware's own runtime state calls for
it: `jump_to_image.S` takes its SRAM-release path when tramp is nonzero
*and* (`!has_el3` or (`has_el3` and `need_to_release_L3_SRAM == 0x41`)).
That has never actually been checked on this device -- it's entirely
possible the fix changed nothing at all, if the real answer is "no
release needed here," which would mean the "raw" path was already
correct and this device's actual blocker is still unidentified.

Added `t7001_sram_check`, another plain, read-only shell command with no
connection to the jump/teardown path -- it reads `id_aa64pfr0_el1` and
the `need_to_release_L3_SRAM` byte directly (the exact two things
`jump_to_image.S` itself checks) and prints them:

```c
void t7001_sram_check() {
    uint64_t pfr0;
    __asm__ volatile("mrs %0, id_aa64pfr0_el1" : "=r"(pfr0));
    int has_el3 = (pfr0 & 0xf000) != 0;
    uint8_t flag = need_to_release_L3_SRAM;
    int would_release = !has_el3 || (has_el3 && flag == 0x41);
    iprintf("id_aa64pfr0_el1=0x%llx has_el3=%d need_to_release_L3_SRAM=0x%02x would_release_via_tramp=%d\n",
            pfr0, has_el3, flag, would_release);
}
```

This is read over the same USB console channel as `help`, no photo
needed. If `would_release_via_tramp=0`, the tramp fix from v4 was a
no-op on this device and the real cause of the hang is still open. If it
prints 1, the tramp fix did change the code path taken, and the hang is
happening somewhere inside (or after) the actual SRAM-release trampoline
itself -- a different, narrower place to look next.

Built from a fresh pinned checkout: 254,032 bytes, SHA-256
`389210235e7234fa33cc473a483ca912bab5fac4ff358d0dc627901a5394ea4d`. All
tests pass. **Not yet run on hardware.**

### v6 hardware run — tramp fix confirmed a no-op on this device (2026-09-03)

`t7001_sram_check` printed, over the plain USB console, no photo needed:

```text
id_aa64pfr0_el1=0x1012 has_el3=1 need_to_release_L3_SRAM=0x69 would_release_via_tramp=0
```

This device has EL3, and its own exploit-stage bootloader patching set
`need_to_release_L3_SRAM=0x69` -- the source's own comment defines that
byte as `0x41 = yes, [anything else] = no`. So `jump_to_image` was
already taking the "raw" (no SRAM release) path on this hardware before
the v4 fix, and still is after it: the fix changed nothing behaviorally
here. It may still be the technically correct call convention (matching
how `exit_to_el1_image` is actually used elsewhere), but it is
conclusively not the explanation for why the marker has never been
observed to execute.

### Where this leaves the project

Six builds, five of them run on real hardware, have now ruled out: wrong
marker size, wrong color, one-shot vs. held vs. strobed writes, timing
too short, and the SRAM-release gap. Every attempt produces the same
shape of result -- PongoOS accepts `linux_t7001`, prints its normal
prep-boot messages, then goes silent and unresponsive with no visible
sign our own code ever ran. The reddish flash turned out to be a real
but unrelated, already-explained display-register side effect of
`linux_prep_boot()` itself, not a clue about the jump.

What's left is genuinely inside `jump_to_image`'s raw path, or in
whatever the CPU's actual state is by the time it reaches our staged
physical address -- cache coherency between the write and the fetch,
exception-level/MMU state assumptions specific to T7001 that a
generalized-for-A10 mechanism doesn't handle, or something not yet
identified. None of that is answerable by more framebuffer experiments;
it needs either a real execution trace (UART/serial console, or
JTAG/SWD via something like a Tamarin cable) or a much deeper, riskier
round of blind ARM64/SoC-internals guessing with a poor track record so
far. This was recorded as an explicit pause point, not a dead end --
and the research below found a better option than either.

### Prior art found: a working reference implementation for this exact chip (2026-09-03)

Requested and completed a research pass across other online projects rather
than continuing to guess blind. Full findings and sourcing in
[`research/t7001-handoff-options.md`](../research/t7001-handoff-options.md);
summary here.

**Konrad Dybcio and Markuss Broks booted mainline Linux on the iPad Air 2
(T7001) in June 2022**, via their own PongoOS fork
([konradybcio/pongoOS](https://github.com/konradybcio/pongoOS)) and kernel fork
([konradybcio/linux-apple](https://github.com/konradybcio/linux-apple)). Their
fork has a dedicated `src/drivers/plat/t7001.c` naming `"Apple A8X (T7001)"` --
this is not a related project, it is a working implementation of the exact
handoff this repo has been trying to build, on the exact chip. Their own
account of the debugging journey (via Hackaday, their original writeup having
since 404'd) describes being blocked for **over a year** by an MMU-enablement
issue, debugging with only framebuffer access (the same constraint faced
here), and the breakthrough being **"a single line difference"** from a
known-working reference.

Diffing their source against this repo's patch surfaced three concrete
differences, most importantly: **their `gEntryPoint` is a fixed constant,
`0x803000000`**, explicitly chosen and validated as a safe contiguous region
across their whole device range (their own comment: "a really hacky
guesstimate, but it works on all devices") -- not a dynamically computed
`alloc_contig()` address the way this repo's patch does it. Second: **their
Linux boot path has no custom `jump_to_image` call or tramp buffer at all** --
`BOOT_FLAG_LINUX` just stages the kernel at that fixed address and falls
through to the same `exit_to_el1_image()` used for XNU boot, the mechanism
already proven to work on this device every time it's jailbroken. Third:
their `linux_boot()` has no `cache_clean()` before the jump either, which
**deprioritizes the "missing cache_clean" theory** from Step 3 above -- a
working implementation doesn't need it, so it's unlikely to be this project's
actual blocker. Their `linux_prep_boot()` also has the identical
`pixfmt0`/color-matrix register poke this project already traced the
reddish-flash artifact to, independently confirming that finding.

### Step 4: adopt the proven reference approach — build verified, not device-tested (2026-09-03)

Implemented the best-evidenced candidate from `research/t7001-handoff-options.md`:
matched `konradybcio/pongoOS`'s approach instead of continuing to iterate on this
project's own custom jump mechanism. Concretely, in `linux_prep_boot()`/
`linux_boot()`/`entry.c`:

- **Fixed entry point.** `gEntryPoint = (void *)0x803000000;` for `socnum == 0x7001`
  (was: whatever `alloc_contig()` happened to return). This is the single biggest
  suspect from the research -- a hand-picked, empirically-safe physical address
  validated by a working implementation on this exact chip, not a heap allocation
  with no particular relationship to firmware-reserved memory.
- **No more custom jump.** `entry.c`'s `BOOT_FLAG_LINUX` case is now just
  `linux_boot();` with no T7001 special-casing -- it falls through to the same
  `exit_to_el1_image()` call used for XNU boot (and, previously, non-T7001 Linux),
  the mechanism proven to work on this device every time it's jailbroken.
  `linux_boot()` itself lost its `if (socnum == 0x7001) return;` early-out, so
  T7001 now does the same `memcpy(gEntryPoint, gLinuxStage, gLinuxStageSize)`
  every other chip does.
- **SEPFW reservation added**, matching the reference: before staging the kernel,
  reserve the ADT's `SEPFW` memory-map region in the Linux DTB via
  `fdt_add_mem_rsv()`, if that region can be found. Soft-fails with a printed
  warning rather than aborting boot if it can't (this project doesn't have the
  device's ADT contents to verify the region exists under this exact name, but
  the call is cheap and matches the reference implementation).
- **Removed entirely**: the custom `jump_to_image`/tramp-buffer call, the
  `gLinuxMarkerStage`/`gLinuxTrampStage`/`gLinuxPrepared` globals, the
  `t7001_boot_marker.S` stub and its staging code, and the `t7001_color_test`/
  `t7001_sram_check` diagnostic commands built to validate that now-abandoned
  approach. `linux_diag`/`linux_diagnostics()` is kept (still a useful, unrelated,
  no-jump upload/DTB sanity check). `linux_t7001` is kept as the explicit,
  deliberately-named command for a real T7001 handoff attempt (still distinct
  from `bootl`, which still refuses T7001 -- the safety boundary of "you must
  explicitly ask for this" is preserved even though the underlying mechanism
  changed).

Net effect: the patch shrank from 684 lines to 449. This is a smaller, more
conservative patch than what it replaces, precisely because it now does *less*
custom work -- it relies on the same shared exit path every other boot type on
this codebase already uses, instead of a bespoke one built and iterated on
without ever getting confirmed evidence it worked.

Built from a fresh pinned checkout: 254,032 bytes, SHA-256
`400161ef9db5c7fa6e7a5a60f2d5044071688fd1bc9964c836f53d3262b51196`.
`boot/test_t7001_pongo_diagnostic.py` and `boot/test_load_linux_diagnostic.py`
still pass unchanged (neither touches the removed marker machinery).
`boot/test_t7001_boot_marker.py` was deleted (tested code that no longer
exists).

### v7 hardware run — same mechanism as XNU boot, same silent hang (2026-09-03)

Launched this build, confirmed `linux_diag` still reports the same staged
addresses (its own local staging, unaffected by the `gEntryPoint` change), then
sent `linux_t7001`. The console confirmed the new code path actually ran:

```text
Booting Linux: 0x803000000(0x805960000)
Booting Linux...
```

`0x803000000` is exactly the new fixed entry point; `0x805960000` is
`gEntryPoint + image_size`, the expected DTB placement. PongoOS then fell
through to `exit_to_el1_image()` -- the literal mechanism proven to work for
XNU/jailbreak boot on this device. Recorded on video for its full 15.5s
duration: **no visible change of any kind**, not even the usual `pixfmt` flash.
The device went to the same enumerated-but-unresponsive state as every prior
real handoff attempt.

This is a genuinely informative negative result: it rules out the entire
category of "our jump/handoff mechanism is wrong," since this attempt used the
literal same mechanism already proven to work for a different boot type on this
exact device. That redirected research toward what happens *after* control
reaches the kernel entry, rather than *how* control gets there.

### Round 2 research: a concrete, unimplemented kernel-DTB gap (2026-09-03)

Requested and completed a second, deeper research pass (full findings, sourcing,
and a project viability assessment in
[`research/t7001-handoff-options.md`](../research/t7001-handoff-options.md)).
Summary of the strongest finding:

Mainline Linux's actual `t7001-air2.dtsi` (Konrad Dybcio's own work was merged
upstream -- confirmed by the `@kernel.org` copyright line) declares `/memory`
and `/reserved-memory` as empty placeholders explicitly commented **"To be
filled by loader."** This project's PongoOS patch never fills them in, beyond
the single `SEPFW` reservation added in Step 4. The pinned upstream PongoOS
revision this project patches has an entire `reserved-memory`-population code
block in `linux_dtree_init()` -- **wrapped in a C block comment, dead code**,
present before any T7001 work by anyone, never enabled by this project's patch
or (as far as could be determined) anyone else's.

Konrad's own *working* PongoOS fills this in for real, with two reservations
computed generically from `boot_args` fields PongoOS already has on every boot
(no per-device hardcoding needed): the framebuffer region
(`gBootArgs->Video.v_baseAddr`, marked `no-map` "so that Linux doesn't
overwrite it") and the low firmware/TZ region from DRAM base up to
`gBootArgs->physBase`. That second one is directly checkable against this
project's own `linux_diag` output -- `phys=0x800c00000` on this exact unit,
meaning **DRAM base plus ~12 MiB is firmware-reserved and currently completely
unprotected** in every build run on hardware so far. Neither gap has ever been
addressed by this project's patch. Without these, Linux's own memory allocator
(active before any driver, before any console) is free to treat that memory --
including the framebuffer's own backing store -- as ordinary allocatable RAM,
which would produce exactly the symptom seen across all six builds: total
silence, no console output, no visible framebuffer change, full hang.

This has **not been implemented or tested** -- it's the top candidate from the
research, not yet acted on. Also unresolved: whether the ADT's `memory-map`
node has other regions beyond `SEPFW` that matter (Konrad's DTSI hardcodes
several more, but those look like per-unit captured values, not something
safely reusable here without independent verification).

### Step 5: reserved-memory / no-map fix implemented — build verified, not device-tested (2026-09-04)

Implemented the top candidate from Round 2 research. It goes in
`linux_dtree_overlay()`, not the dead `linux_dtree_init()` -- checked first and
confirmed `linux_dtree_init()` never actually runs in this project's real boot
flow: `fdt_initialized` is only false if no DTB pack was uploaded, and
`load_linux.py` always uploads one before `linux_diag`/`linux_t7001`, so the
real path is always `linux_prepare_fdt()` → `linux_dtree_overlay()` operating on
the actual kernel-built DTB (which has the real, empty `/reserved-memory` node
from mainline). Adding the reservations to the from-scratch dead function would
have built and tested cleanly while fixing nothing.

Added, after the existing `/chosen` bootargs/initrd handling in
`linux_dtree_overlay()`:

```c
node = fdt_path_offset(dtree, "/reserved-memory");
if (node < 0)
{
    iprintf("Failed to find /reserved-memory; the Linux DTB may let the kernel overwrite firmware-reserved memory and the framebuffer.\n");
}
else
{
    siprintf(fdt_nodename, "/memory@%lx", gBootArgs->Video.v_baseAddr);
    node1 = fdt_add_subnode(dtree, node, fdt_nodename);
    fdt_appendprop_addrrange(dtree, 0, node1, "reg", gBootArgs->Video.v_baseAddr,
                              gBootArgs->Video.v_height * gBootArgs->Video.v_rowBytes);
    fdt_appendprop(dtree, node1, "no-map", "", 0);

    if (gBootArgs->physBase > 0x800000000)
    {
        node1 = fdt_add_subnode(dtree, node, "memory@800000000");
        fdt_appendprop_addrrange(dtree, 0, node1, "reg", 0x800000000,
                                  gBootArgs->physBase - 0x800000000);
        fdt_appendprop(dtree, node1, "no-map", "", 0);
    }
}
```

(error handling on the `fdt_add_subnode` calls elided above for brevity; the
actual patch checks each one). Both reservations are computed from `boot_args`
fields PongoOS already has on every boot -- no per-device hardcoded addresses,
unlike the several extra regions Konrad's own DTSI hardcodes that this project
still hasn't independently verified. This runs unconditionally for every chip
PongoOS boots Linux on, not just T7001 -- it's a general correctness fix
matching mainline's own "to be filled by loader" contract, not a T7001-specific
workaround.

Also noted, not yet fixed (separate, lower-priority, correctness-only bug):
this function creates a top-level `/framebuffer@<addr>` node, but mainline's
actual DTS has the framebuffer placeholder *inside* `/chosen`
(`chosen/framebuffer@0`, `status = "disabled"`, `reg` and format "to be filled
by loader"). This project's code never finds/fills that real placeholder --
it adds a differently-placed node instead. Unlikely to explain the current
silent-hang symptom (a misplaced framebuffer node should mean "no display
driver probes," not "kernel never produces any output at all," including
console/earlycon), so left alone for this change to stay narrowly scoped to
one variable. Worth fixing before framebuffer console output is expected to
work, once boot itself succeeds.

Built from a fresh pinned checkout: 254,032 bytes, SHA-256
`07cde808723eb1c1761fb847200b53803a0da953e1579fb0ae546d12affff0cf`. All
existing tests pass unchanged. Added `boot/test_t7001_reserved_memory.py`
(structural checks: looks up the real DTB's existing node rather than
creating one, both reservations computed from `boot_args` not hardcoded,
both marked `no-map`).

### Pre-hardware code review, cross-checked against Asahi Linux/m1n1 (2026-09-04)

Requested before running this build on hardware: a review for dead code and
correctness, plus a check against `AsahiLinux/m1n1` (supports newer Apple
Silicon, far more mature than the 2022 konradybcio fork) for anything done
materially differently. Full writeup in
[`research/t7001-handoff-options.md`](../research/t7001-handoff-options.md)
("Round 3"); summary:

**No blocking bug found.** Three non-blocking notes: `linux_dtree_init()`/
`linux_dtree_late()` are confirmed unreachable in this project's real flow
(verified while writing Step 5) and diverge from every fix applied so
far -- a real footgun if `linux_t7001` is ever run without first uploading a
DTB pack via `fdt`, but not something that has affected any attempt to date;
`gLinuxDtb`/`gLinuxStageAllocation` are wider-scope globals than needed now
that Step 4 removed their other callers; `gLinuxStageAllocation` leaks if
`linux_prep_boot()` runs more than once per session (hasn't happened in any
attempt so far). None changed, to keep this hardware round scoped to the
Step 5 fix alone.

One thing that looked like a bug and wasn't: the framebuffer reservation's
node name has a leading slash added to a non-root parent, which libfdt's
`fdt_add_subnode` (checked directly) doesn't validate or strip. Konrad's
proven-working reference has the exact same leading slash in the exact same
place -- left as-is, matching it bug-for-bug, since Linux's reserved-memory
scan works structurally (parent-child + `reg`/`no-map`), not by name.

**Asahi/m1n1 cross-check increased confidence rather than finding a gap.**
`m1n1` does the same class of ADT-to-`/reserved-memory` conversion via a
generic helper -- confirms this project's fix matches current, mature
community practice, not an ad-hoc guess. It also revealed a nuance this
project's *existing* (Step 4) SEPFW handling already gets right without
anyone realizing it: m1n1 deliberately does *not* mark its SEP reservation
`no-map` (SEP communication needs it in Linux's normal linear map), and this
project's `fdt_add_mem_rsv()`-based SEPFW reservation has the same effect for
the same reason, independent of Step 5. The framebuffer/low-FW `no-map`
choice also matches the documented upstream `simple-framebuffer` binding
convention. Ready to test.

## Playbook: next hardware session

Written 2026-09-04, before a break with the Step 5 build built, reviewed, and
ready but not yet run on hardware. Self-contained -- shouldn't require reading
the rest of this file to act on.

### Setup

Binary ready to flash: `boot/Pongo-t7001-diagnostic.bin`, SHA-256
`07cde808723eb1c1761fb847200b53803a0da953e1579fb0ae546d12affff0cf` (Step 5:
framebuffer + low-firmware `no-map` DTB reservations; passed a full code
review in Round 3, cross-checked against Asahi Linux/m1n1). Confirm the file
on disk still matches that hash before flashing (`shasum -a 256
boot/Pongo-t7001-diagnostic.bin`) -- if it doesn't, something rebuilt it;
check `git log -- boot/pongo-t7001.patch` for what changed.

```bash
sudo /tmp/palera1n-arm64 --pongo-shell --override-pongo "/Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos/boot/Pongo-t7001-diagnostic.bin" --debug-logging
```

Two replugs, direct into the Mac (no hub/dock): once right after `Checkmate!`
/"reconnect in download mode", once more when the PongoOS logo actually
appears on screen. Confirm enumeration (`idVendor=0x05ac, idProduct=0x4141`)
and a `help` response before doing anything else -- see any prior "Launch
this build" step above for the exact PyUSB snippets.

Then:
1. `linux_diag` via `load_linux.py --diagnostic ...` first, as a sanity check
   -- unaffected by the Step 5 change, should reproduce the same measured
   addresses recorded in every prior verified run.
2. With the device watched **and recorded on video** the whole time, send
   `linux_t7001` via `load_linux.py --t7001-handoff ...`.

### Step 5 hardware result (2026-09-04): tried, same silent hang

Run for real. `linux_diag` reproduced the same measured contract as every
prior verified run. `linux_t7001` was sent, recorded on video (10.8s,
120fps) and confirmed via a full-resolution photo: the console reached the
identical point as the Step 4 run --
`Booting Linux: 0x803000000(0x805960000)` then `Booting Linux...` -- then
went silent. No boot log, no panic, no visible framebuffer change of any
kind, not even the usual `pixfmt` reddish flash and even that fell in the
same place as prior runs when it was noticed. Device left enumerated but
unresponsive, same as every real handoff attempt so far.

(A first read of a low-resolution extracted video frame briefly looked like
it stopped *before* those two lines -- a fresh high-resolution photo the
user sent right after corrected this. Worth remembering for next time:
don't conclude a *shorter* console transcript than a prior run from a
downscaled/compressed frame alone; get a full-resolution capture before
drawing that conclusion, since it changes the diagnosis materially.)

**This is the "if it still hangs" case** -- the reserved-memory fix, while
well-evidenced and cross-checked against two working reference
implementations (Round 3), was not sufficient on its own. Jump to
"If it still hangs silently" below for the ranked next steps; candidate 1
there (generic ADT `memory-map` enumeration) is the next thing to try,
not yet built.

### If you see anything that isn't the exact PongoOS logo screen

Boot log lines, a kernel panic, garbled text, a color change that holds, a
crash dump -- anything at all. Treat this as the actual milestone:

1. **Stop and capture first.** Photo and video everything immediately, before
   the device potentially locks up or the moment passes. Do not send another
   command until it's documented.
2. Read how far it got, since the response differs by case:
   - **Boots to a shell/login prompt or keeps producing kernel log lines** --
     console works. This is the "first technical success" the project's own
     Mission section has been chasing. Record it as its own dated section
     here with the full transcript/photos, and update the "Current state at a
     glance" table.
   - **A kernel panic with a backtrace** -- also a real win, not a failure:
     it proves the CPU executed real kernel code after the handoff, further
     than any of the six prior attempts got. Transcribe or photograph the
     *entire* panic text, including the register dump and call trace if
     shown -- that tells you exactly what to fix next (a missing driver, a
     bad memory access, etc.), which is a completely different and much
     easier kind of debugging than "silent hang, no information" has been.
   - **A few log lines then it stops** -- note the exact last line printed;
     that names the next subsystem to investigate.
3. Once any of the above is confirmed, this project's own **"Driver readiness
   and approval gate"** section (below) applies as written: it requires
   explicit user approval before implementing or fixing any specific driver
   (touch, Wi-Fi, etc.), even though the primary PongoOS→Linux gate that
   section was written behind has now been cleared. Don't start driver work
   without that approval just because boot succeeded.
4. Worth fixing now that iteration is real again: the `/chosen/framebuffer`
   placement mismatch noted in Step 5 (needed for a working framebuffer
   console), and the `linux_dtree_init()` dead-path footgun noted in Round 3
   (make `linux_t7001` refuse to run without an uploaded DTB pack, or remove
   the dead from-scratch path entirely).

### If it still hangs silently, identical to every attempt so far

Ranked by cost, cheapest and most-evidenced first. Treat each as its own
single-variable test, same discipline as every step so far -- don't bundle
more than one at a time, or a positive result won't tell you which change
mattered.

1. **Generically enumerate the ADT's `memory-map` node**, not just the three
   regions (`SEPFW`, framebuffer, low-FW) reserved so far. PongoOS already has
   a generic node/property walker, `dt_parse()` (`src/kernel/dtree.c`,
   declared in `pongo.h`) -- use it to iterate every property under
   `memory-map` and reserve each one (via `fdt_add_mem_rsv` or a
   `/reserved-memory` `no-map` subnode, matching the pattern already in
   `linux_dtree_overlay()`), rather than hand-picking names. This directly
   tests whether Konrad's several extra hardcoded regions
   (`0x870100000`/`0x870180000`/three more in `research/t7001-handoff-options.md`)
   matter too, without reusing his possibly-per-unit constants directly. Not
   yet built.
2. **Fix the `/chosen/framebuffer` placement bug** alongside (1) -- low
   priority for a silent-hang specifically (a misplaced node should mean "no
   display driver probes," not "total silence"), but cheap to remove as a
   variable while already in this code.
3. **Check the postmarketOS wiki device page manually** in a real browser --
   automated fetching was blocked by an anti-bot challenge throughout this
   research (`wiki.postmarketos.org`, device likely `apple-ipad5,3` /
   `apple-j81`). Free, no hardware cost, and independently informative either
   way: confirms whether this general technique still works today on *any*
   implementation, not just this one.
4. **A kernel-embedded marker** -- a new idea, not yet designed in detail or
   built. If (1)-(3) don't resolve it, the next diagnostically useful step
   is combining the now-proven exit path with real observability: inject a
   tiny stub directly at the fixed entry point (`0x803000000`) that writes a
   marker to the framebuffer, then falls through to the real kernel Image's
   own first instruction -- unlike the abandoned Step 1-3 marker, this runs
   through the actual `exit_to_el1_image()` path in the exact position Linux
   itself would occupy, rather than a separate custom jump. Needs care to not
   corrupt the Image's own header (`text_offset` and size fields live at
   fixed offsets from the Image start) -- prepend a few instructions and
   branch forward past them, don't overwrite anything the AArch64 boot
   protocol or the kernel's own early code depends on.
5. **UART/serial console, or JTAG/SWD** (e.g. a Tamarin-style cable) -- needs
   hardware not currently available. The fallback once (1)-(4) are tried and
   still produce no new information; see the Round 2 viability assessment in
   `research/t7001-handoff-options.md` for the reasoning on when to treat
   this as genuinely blocked on tooling rather than more inference.

Only after a visible Linux log, resume the console, touch, and Wi-Fi work
recorded below. The current driver approval gate remains in force regardless
of which branch above applies.

## Driver readiness and approval gate (2026-09-02)

This is an evidence-based planning record, not authorization to change a
driver, device tree, PongoOS, or firmware. **Wait for explicit approval before
implementing or fixing any item below.** Every subsystem is untested in Linux
until the T7001 PongoOS handoff above produces a Linux log.

The current 6.19.3 kernel configuration is useful infrastructure, but it is
not a hardware-support claim. The generated `t7001-j81.dtb` contains the
basic AIC, UART, watchdog, pinctrl, PMGR/I2C, simple framebuffer and GPIO-key
nodes. It contains no USB controller, touch/SPI peripheral, Wi-Fi/SDIO, or
Bluetooth peripheral node. The initramfs packages `kmod` programs but no
`/lib/modules` tree, so configured modules cannot currently be loaded there.

| Subsystem | Current state | Missing or broken prerequisite | Planned work after approval |
| --- | --- | --- | --- |
| PongoOS → Linux | **Broken; primary gate** | The matching PongoOS Linux module supports A10 only and uses an A10-specific entry address. The T7001 returns to PongoOS after `bootl`. | Instrument and port the handoff before debugging a Linux driver. |
| Console / USB gadget | **Not described by J81 DTB** | DWC2 and USB gadget support are configured, but there is no T7001 USB controller/UDC node, clocks, PHY or interrupt wiring in the generated DTB. | Add only the verified controller description; use a serial or USB console before networking work. |
| Display | **Unverified** | A simple framebuffer is described, but Linux has not reached it. Native display, backlight and acceleration support are absent. | Validate the inherited framebuffer after first boot; keep native DRM out of the near-term scope. |
| Touchscreen (BCM5976) | **Blocked; priority 1** | No T7001 SPI-controller or touchscreen DT node, reset/IRQ/power mapping, firmware, or calibration data. Upstream `apple_z2` currently binds only two Mac Touch Bar compatibles, not an iPad. | Establish the Air 2 wiring and protocol first, then make an iPad-specific adaptation only if the evidence supports it. |
| Wi-Fi (BCM4354) | **Blocked; priority 2** | `brcmfmac` includes BCM4354 and SDIO support, but J81 has no SDIO host/module node, power/reset mapping, board NVRAM or firmware. `brcmfmac`/`cfg80211` are modules outside the initramfs. | Identify and expose the SDIO host, then integrate the required local firmware/NVRAM and modules. |
| Bluetooth (BCM4354 combo) | **Blocked** | `hci_uart`/`btbcm` infrastructure exists, but its UART, flow control, power sequencing, firmware and DT node are unknown; its modules are also absent from the initramfs. | Defer until Wi-Fi has identified the Murata module's power and board wiring. |
| Audio | **No known T7001 stack** | Audio DMA, codec identity/register map, machine description and power routing are absent. | Defer. |
| Battery / PMIC | **Partial generic support only** | The BQ27xxx driver exists, but no fuel-gauge DT node; the Apple/ Dialog PMIC and charging path lack a supported description. | Probe the standard fuel gauge only after I2C and power topology are mapped. |
| Sensors | **Unknown** | Generic IIO drivers exist, but the sensor chips and their I2C/SPI/M8 path are unidentified and no nodes exist. | Inventory from an Apple device tree before selecting a driver. |
| GPU | **No Apple A8X integration** | No supported PowerVR A8X DRM/platform backend. | Use framebuffer/software rendering only; defer acceleration. |
| NAND / cameras / Touch ID | **Unsupported** | Apple storage FTL/encryption, camera ISP paths and Secure Enclave interfaces have no usable Linux path. | Out of scope for the RAM-only milestone. |

### Priority bring-up plan

1. **Restore an observable boot path.** Re-enter DFU, relaunch PongoOS with the
   known command, and make the small instrumented T7001 PongoOS fork described
   above. Do not retry a stock `bootl` upload or diagnose touch/Wi-Fi before a
   Linux log exists.
2. **Create a console before a network dependency.** Use the Pongo/Linux
   display or UART output first. Port the USB controller/UDC description only
   from verified T7001 register, clock, PHY and interrupt data; then test the
   built-in gadget path.
3. **Touch evidence phase.** From a user-supplied iPad Air 2 IPSW and Apple
   device tree, record the actual SPI controller, chip select, reset, IRQ,
   power sequence, firmware name and calibration source. Compare the observed
   initialization and report frames with `apple_z2`; its protocol code is a
   reference, not a drop-in BCM5976 binding. Do not commit Apple firmware or
   per-device calibration material.
4. **Wi-Fi evidence phase.** Identify the BCM4354 SDIO host, pins, reset and
   power sequencing from the same board data. First prove that Linux enumerates
   an SDIO function. Only then package the minimum module closure plus the
   user-provided firmware, board NVRAM and regulatory data locally; do not add
   proprietary blobs to Git.
5. **Approval checkpoint.** Present the extracted hardware facts, proposed
   DT changes and test image for review. Start touch or Wi-Fi implementation
   only after the user explicitly approves it.

Authoritative source checks: the [6.19.3 `apple_z2` match table](https://github.com/torvalds/linux/blob/v6.19.3/drivers/input/touchscreen/apple_z2.c)
contains only `apple,j293-touchbar` and `apple,j493-touchbar`; the
[brcmfmac chip table](https://github.com/torvalds/linux/blob/v6.19.3/drivers/net/wireless/broadcom/brcm80211/brcmfmac/chip.c)
does include BCM4354. The current upstream [J81 device tree](https://github.com/torvalds/linux/blob/v6.19.3/arch/arm64/boot/dts/apple/t7001-j81.dts)
is the reference for the intentionally minimal board description.

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
| Current RAM-only Pongo session | ✅ Active after verified handoff-candidate diagnostic; transient and RAM-only |
| Linux payload upload | ✅ Transferred once; exposed PongoOS pre-handoff defects |
| Guarded T7001 diagnostic PongoOS | ✅ Matched-toolchain Pongo, USB, aligned Image/DTB/initrd ranges, Linux register contract, and no-jump guard are proven on T7001 |
| Linux kernel boot | ❌ Not achieved; 7 hardware handoff attempts, all silent hangs; color/timing/SRAM-release/jump-mechanism/reserved-memory all tried and ruled out or insufficient alone; next candidate is generic ADT memory-map enumeration — see research/t7001-handoff-options.md and the Playbook section |
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
