# Software-only T7001 control

This is the last well-evidenced experiment that does not require a custom
UART/JTAG cable. It reproduces the complete June 2022 stack that was reported
working on A7/A8/A8X, including the iPad Air 2, before mixing in the current
kernel, NixOS initramfs or the project's diagnostic PongoOS changes.

## Why this is new

Earlier hardware rounds copied selected changes from the historical PongoOS
fork into a modern tree. They did **not** run the historical tree, kernel and
published initramfs together. A fresh audit found two important gaps:

1. The 2022 PongoOS `messy but works` change spans twelve files. Besides its
   fixed `0x803000000` entry point, it changes mappings, MMU/heap setup, stage 3,
   entry assembly and CPU state at the handoff boundary. Our patch reproduced
   only selected visible differences.
2. The canonical HOWTO requires a **4 KiB** Linux page size for A7–A8X. This
   project had incorrectly selected 16 KiB, which the same guide assigns to A9
   and newer. That error would matter after the kernel starts, although it does
   not by itself explain why the entry marker never ran.

The control therefore keeps the known stack intact. If it boots, change one
layer at a time: userspace/initramfs first, current 4 KiB kernel second, and
PongoOS last.

## Exact inputs

| Component | Revision / SHA-256 |
| --- | --- |
| `konradybcio/pongoOS`, branch `a7` | `a3b1f652f691ff35ad1cd7840f3dfe11afdd82c9` |
| Built `Pongo.bin` | not byte-reproducible -- see note below (708,704 bytes) |
| `konradybcio/linux-apple`, branch `apple/v5.19-rc1` | `a907b05f09bfea50511ea0e82dc14f70d999ba37` |
| `SoMainline/linux-apple-resources` | `30780ec0fecdab849bb812e1dde52b87e614f45b` |
| Published `example.config` | `5cbfbfa416638f4f9e27df614b7b2e05b3b4e7b9fd66aeecad5283ccb37c6f36` |
| Published `dtbpack.sh` | `6447a921d8dbdd2f84785b177daac397e87210239dbea409a0bcde1dc2bc485d` |
| Published `debug_initrd.img` | `af3fc3c7c57c775095fea2df7930961c92f73ec95f64d4c7ef6cae9c02dee9c6` (1,299,789 bytes) |

The revision and every published-file hash above were independently
re-verified against the real repositories (fresh clone, `shasum -a 256`) and
match exactly.

**`Pongo.bin` does not build byte-reproducibly**, unlike every other build
this project has pinned by hash. Built it twice from independent clean-room
clones of the exact same commit, same toolchain (Apple Clang 14.0.0 /
Xcode 14.2 ld64-820.1): both runs produced a 708,704-byte binary, but two
different SHA-256 hashes, neither matching a third hash an earlier pass
through this same procedure had recorded here. Almost certainly `-flto`
nondeterminism in the 2022 Makefile itself (not something this project's
one-line Clang-14 compatibility flag introduces) -- this project's own
patched-PongoOS builds *are* byte-reproducible across independent clones, so
this is a real difference in the historical branch, not a broken process.
Verify this control build by source revision + successful build + correct
size, not by a fixed output hash; a hash match here would be a coincidence,
not a correctness signal.

The Nix lock file pins the kernel and resources. The PongoOS helper rejects a
dirty or wrong source revision and a wrong Apple toolchain.

## Build the payload

From the repository root on the Mac:

```bash
nix build .#packages.x86_64-linux.historical-payload \
  -o result-historical-payload -L
```

The result contains `Image.lzma`, the published multi-device `dtbpack`, and the
published `initrd`. The Linux build uses the resources repository's published
`example.config`, including 4 KiB pages, rather than the modern project
configuration or the branch's broader generic `defconfig`.

## Build the historical PongoOS image

Use a fresh source tree and Apple Command Line Tools 14.2. Point the two
variables at the `clang` and `ld` binaries in that extracted toolchain:

```bash
git clone --recurse-submodules --branch a7 \
  https://github.com/konradybcio/pongoOS.git /tmp/pongo-a7-control
git -C /tmp/pongo-a7-control checkout \
  a3b1f652f691ff35ad1cd7840f3dfe11afdd82c9

PONGO_CC=/path/to/CommandLineTools/usr/bin/clang \
PONGO_LD=/path/to/CommandLineTools/usr/bin/ld \
  ./boot/build-pongo-t7001-historical.sh /tmp/pongo-a7-control
```

The only compatibility flag added by the helper is
`-Wno-unused-but-set-variable`. Apple Clang 14 turns two harmless historical
warnings into errors; suppressing that diagnostic leaves the source and
generated behavior unchanged.

## Hardware run

Do this only when all four files above exist and their hashes are checked.
Start from DFU and use the same standalone palera1n path already proven on this
Mac:

```bash
sudo /tmp/palera1n-arm64 --pongo-shell \
  --override-pongo "$PWD/boot/Pongo-t7001-historical.bin" \
  --debug-logging
```

The Apple Silicon flow has required two Lightning reconnects: once after
`Checkmate!` / the download-mode prompt, and again when the Pongo logo appears.
Confirm that USB `05ac:4141` answers before uploading anything. Then use the
loader from the same historical checkout:

```bash
python3 /tmp/pongo-a7-control/scripts/load_linux.py \
  -k result-historical-payload/Image.lzma \
  -d result-historical-payload/dtbpack \
  -r result-historical-payload/initrd
```

The loader's `Success.` message only means the USB control transfer disconnected;
it is not boot evidence. Success means Linux output or the initramfs is visibly
reached on the iPad framebuffer.

## Decision after the run

- If it boots, preserve the exact control artifacts and replace only the
  initramfs with the project image. Next test the current kernel with its fixed
  4 KiB configuration. Port PongoOS only after those two tests.
- If it fails identically, stop software-only handoff patching. Without UART or
  JTAG there is no independent signal left at the failing boundary, and more
  blind variants would be poor-value speculation.
- Touch and Wi-Fi remain approval-gated and are out of scope until Linux runs.

## A second, architecturally different route: PongoOS's own `bootm` -> m1n1

This is **not** a control in the same sense as the section above -- it does not
reproduce a state anyone has confirmed working on this exact chip. It is a
new, well-evidenced experiment: instead of jumping from PongoOS straight to
Linux (the mechanism behind all seven hypotheses already ruled out, including
every version of this project's own `bootl`-based patch), load
[m1n1](https://github.com/AsahiLinux/m1n1) -- Asahi's own bootloader, adapted
by [HoolockLinux](https://github.com/HoolockLinux) for A7-A11 iDevices -- as
an independent intermediate stage between PongoOS and Linux.

**Why this is real, not another guess at the same mechanism** (each fact
independently verified against the primary source, not taken from any
secondary writeup):

- PongoOS has a genuine, dedicated `bootm` command --
  `command_register("bootm", "boots m1n1", pongo_boot_m1n1)` -- on the
  `checkra1n/PongoOS` **`iOS15`** branch. This project's own pinned base
  revision (`742d92a023d16c4cc9ebf9cb73b708bf92c52808`) is a direct git
  ancestor of `iOS15`; `bootm` was added later on the same lineage
  (`e1313a7 Add m1n1 boot support`, `bb492b0 Load m1n1 at top of kernel
  data`), not on some unrelated fork.
- HoolockLinux's m1n1 fork has genuine, specific T7001/A8X awareness:
  `#define T7001 0x7001` and `MIDR_PART_T7001_TYPHOON` appear directly in
  its source (`src/soc.h`, `src/midr.h`), on a branch literally named
  `idevice`.
- The prebuilt `Pongo.bin` this package uses
  (`HoolockLinux/docs/binaries/Pongo.bin`) was confirmed, by reading its own
  embedded version string (`pongoOS 2.6.3-bb492b00`), to be built from
  exactly commit `bb492b0` -- the "Load m1n1 at top of kernel data" commit
  identified above. Not an unrelated or stale build.

**What is not yet known**: whether m1n1, once loaded via `bootm`, actually
completes a Linux boot on *this* device. HoolockLinux's own project status
describes the port as not yet at general-use maturity. This is a genuinely
open experiment, not a second control -- but it exercises a completely
different, independently-engineered handoff path than anything tried in
Steps 1-7, so a result here (success or a *different* failure mode) would be
new information regardless.

### Build and inputs

```bash
nix build .#packages.x86_64-linux.m1n1-control -o result-m1n1-control -L
```

Produces `Pongo.bin` (HoolockLinux's, pinned to commit `bb492b0` per the
version-string check above), `m1n1.bin` (from a pinned GitHub Actions
artifact, `HoolockLinux/m1n1` run `33380676898`, branch `idevice`), and
`m1n1-linux.bin` -- m1n1 concatenated with a bootargs string, the historical
control kernel's `t7001-j81.dtb`, its `Image.gz`, and the published debug
initramfs, in the exact order `HoolockLinux/docs`'s own
`tutorials/SETUP_pongoOS.md` documents. All three source fetches (`linux-
apple`, `linux-apple-resources`, `hoolockDocs`, `hoolockM1n1`) are locked
flake inputs, resolved on the Mac rather than fetched from inside the
offline cross-compilation builder -- see "Attempts and failures" below for
why that distinction matters.

### Hardware run

```bash
sudo /tmp/palera1n-arm64 --pongo-shell \
  --override-pongo "$PWD/result-m1n1-control/Pongo.bin" --debug-logging
```

After the usual two-replug sequence and confirming `05ac:4141` answers:

```bash
python3 boot/load_m1n1.py result-m1n1-control/m1n1-linux.bin
```

`bootm was accepted` only means the USB control transfer completed; it is
not boot evidence, same caveat as every other loader in this project.
Success means m1n1's own output, or Linux's, is visibly reached on the
iPad's framebuffer.

## Attempts and failures while preparing the control

- Building the historical PongoOS source with Apple Clang 14 initially failed
  because two unused-but-set warnings were promoted to errors. The narrow
  warning suppression above produced the pinned 708,704-byte binary.
- The first Nix kernel attempt let the offline Linux builder fetch GitHub and
  failed on DNS. Moving both source trees to locked flake inputs makes Nix fetch
  them on the Mac and copy them to the builder.
- A subsequent build used the kernel branch's generic `defconfig`. Inspection
  caught that it omitted the HOWTO's simple framebuffer and watchdog choices
  and enabled thousands of unrelated options. It was stopped before completion;
  the package now installs and uses the published `example.config` unchanged.
- The first source-preparation derivation removed executable bits while making
  the immutable source writable, so Kconfig could not run its helper scripts.
  Preserving modes and adding only owner write permission fixed it.
- `nix flake check --no-build` passes for the native macOS outputs. With
  `--all-systems`, all packages evaluate but the pre-existing x86_64 Linux
  devenv shell fails because devenv cannot determine its current directory;
  this is unrelated to either control package.
- Earlier rounds are still valid evidence about the modern patched stack; they
  are not evidence that this complete historical stack was tried.
- **The historical `Pongo.bin` build is not byte-reproducible.** Independently
  rebuilt it twice from fresh clean-room clones of the exact same pinned
  commit, same toolchain -- got two different SHA-256 hashes (708,704 bytes
  both times, matching a third, also-different hash an earlier pass had
  recorded). Almost certainly `-flto` nondeterminism in the 2022 Makefile
  itself, not something this project's one-line Clang-14 compatibility flag
  introduces -- this project's own patched-PongoOS builds *are*
  byte-reproducible across independent clones, so this is a genuine
  difference in the historical branch. Verify this control by source
  revision + successful build + correct size, not a fixed output hash.
- `m1n1-control`'s first build attempt failed for the same DNS reason as the
  kernel sources above: `hoolockM1n1` was fetched via `pkgs.fetchzip` inside
  the package body, which runs on the offline cross-compilation builder (no
  route to `nightly.link`/`tarballs.nixos.org`). Moved it to a locked flake
  input (resolved on the Mac, like `linuxApple519`/`linuxAppleResources`),
  after which the build succeeded end-to-end.
- `boot/load_m1n1.py`'s upload sequence was missing the "discard any
  previously buffered upload" USB request (`bRequest 2`, `wLength 0`) that
  `boot/load_linux.py` always sends first. Not fatal on a completely fresh
  boot (PongoOS's own receive buffer already starts empty), but a real gap
  versus this project's established, safer pattern -- fixed to match.

## Primary references

- [SoMainline build and boot HOWTO](https://github.com/SoMainline/linux-apple-resources/blob/30780ec0fecdab849bb812e1dde52b87e614f45b/HOWTO.md)
- [Historical PongoOS `a7` branch](https://github.com/konradybcio/pongoOS/tree/a3b1f652f691ff35ad1cd7840f3dfe11afdd82c9)
- [Historical Linux branch](https://github.com/konradybcio/linux-apple/tree/a907b05f09bfea50511ea0e82dc14f70d999ba37)
- [checkra1n/PongoOS `iOS15` branch](https://github.com/checkra1n/PongoOS/tree/iOS15) --
  adds `bootm`/m1n1 support on top of this project's own pinned base revision
- [HoolockLinux](https://github.com/HoolockLinux) and
  [HoolockLinux/docs](https://github.com/HoolockLinux/docs) -- Linux on
  A7-A11/T2 iDevices, m1n1-based
- [HoolockLinux/m1n1](https://github.com/HoolockLinux/m1n1), branch `idevice` --
  the T7001/A8X-aware m1n1 fork
