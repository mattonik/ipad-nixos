# Software-only T7001 control

**2026-09-07: Linux boots.** The `bootm` -> m1n1 route below (not the
historical-control route this document was originally written around --
see "A second, architecturally different route" further down) got Linux
running on this exact iPad Air 2, confirmed by genuine kernel driver-probe
output captured on video. See "Hardware round, 2026-09-07" under that
section for the full transcript and how it was verified. This is the
project's primary milestone to date.

This document originally centered on reproducing the complete June 2022 stack
reported working on A7/A8/A8X. That historical-Pongo route remains blocked by
a `palera1n` size limit. The active software-only path is now the successful
PongoOS `bootm` -> m1n1 route plus the console/initramfs experiments documented
below; it does not require a custom UART/JTAG cable.

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

**2026-09-07: this control could not be attempted as documented.**
`palera1n`'s checkm8 stager rejects the historical `Pongo.bin` outright:

```
Error: PongoOS image is too large: must be at most 0x7fe00, have 0xad060
Failed preparing stage3! (error code: -status_resources_load_failed)
```

0x7fe00 = 523,776 bytes; the historical build is 708,704 bytes (0xad060) --
about 185 KB over. This project's own modern diagnostic build (270,416 bytes)
and the m1n1 route's prebuilt `Pongo.bin` (238,096 bytes) are both
comfortably under the limit, so this is specific to the historical `a7`
branch's build -- likely from the much broader set of platform drivers and
XNU/SEP/IMG4 handling code it compiles in (see the build command in
"Attempts and failures" below) that this project's own patched build doesn't
carry. Not yet investigated further -- pivoted to the m1n1 route below
instead of spending the same DFU cycle on it. Revisit by either trimming the
historical build's compiled-in driver set (tension: that stops being an
exact reproduction of the 2022 stack) or finding whether `palera1n` has an
undocumented flag or an alternate stager path without this limit.

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
`m1n1-linux.bin` -- m1n1 concatenated with a newline-terminated bootargs
string, `t7001-j81.dtb`, `Image.gz` (both from the historical control
kernel), and the published debug initramfs, in the exact order
`HoolockLinux/docs`'s own `tutorials/SETUP_pongoOS.md` documents. All source
fetches (`linux-apple`, `linux-apple-resources`, `hoolockDocs`,
`hoolockM1n1`) are locked flake inputs, resolved on the Mac rather than
fetched from inside the offline cross-compilation builder -- see "Attempts
and failures" below for why that distinction matters.

**As of the 2026-09-07 hardware round below, the DTB in this payload is the
*modern* kernel's `t7001-j81.dtb` (mainline-sourced), not the historical
kernel's own bundled one** -- the historical DT's CPU nodes use a format
that crashes m1n1's CPU bring-up; see that section for the exact bug. The
kernel *Image* is still the historical, pinned 5.19-rc1 build.

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

### Hardware round, 2026-09-07: m1n1 boots. Two real bugs found and fixed, live

The historical-control DFU cycle above hit the palera1n size-limit blocker
and couldn't be attempted at all, so this round tried the m1n1 route
instead -- its `Pongo.bin` (238,096 bytes) is well under the limit.

**Attempt 1** (before either fix below): payload uploaded (12,575,458 bytes),
`bootm` sent, PongoOS disconnected. On screen, m1n1 (`d5a10ac`) printed its
full banner, read `boot_args` correctly (`phys_base: 0x800c00000`,
`mem_size: 0x7c4de000` -- matching every prior PongoOS diagnostic run
exactly), then: `Checking for payloads... Devicetree compatible value:
apple,j81` followed immediately by `Unknown payload at 0x803b8c000 (magic:
63686f73)` and `No valid payload found`. `0x63686f73` is ASCII `chos` -- the
start of this project's own `chosen.bootargs=...` line.

Root cause, from `src/payload.c`'s `check_var()`: it parses a
`chosen.X=value` line by finding `=`, then requires a trailing `\n` to
locate the end of `value` (`memchr(val, '\n', ...)`); without one it returns
`false` and the parser falls through to "unknown payload", using whatever
bytes sit at the start of the whole remaining blob. This project's Nix
recipe built the file with `printf '%s' '...'` -- no trailing newline. Fixed
to `printf '%s\n' '...'` (see `flake.nix`).

**Attempt 2** (newline fix only): uploaded 12,575,459 bytes (exactly one
more, as expected), `bootm` sent. This time m1n1 got dramatically further --
the single most information-dense result this entire investigation has
produced:

```
Found a variable at 0x803b8c000: chosen.bootargs=console=tty0 loglevel=8 ignore_...
Found a devicetree for apple,j81 at 0x803b8c045
Found a gzip compressed payload at 0x803b8ddcb
Uncompressing... 10072011 bytes uncompressed to 24309768 bytes
Found kernel at 0x805400000
Found a gzip compressed payload at 0x804528d96
Uncompressing... 1299789 bytes uncompressed to 2266748 bytes
Found a cpio initramfs at 0x806c00000
No more payloads at 0x8046662e3
cpufreq: Initializing clusters
Starting secondary CPUs...
Starting CPU 1 (0:0:1)... Started.
Starting CPU 2 (0:0:2)... Started.

CPU vulnerability status:
  gofetch: Not vulnerable

FDT: asahi,m1n1-stage1-version = 'd5a10ac'
FDT: bootargs = 'console=tty0 loglevel=8 ignore_logic rdinit=/init'
FDT: initrd at 0x806c00000 size 0x22967c
FDT: No framebuffer found
ADT: 64 bytes of random seed available
FDT: KASLR seed initialized
FDT: Passing 64 bytes of random seed
FDT: reporting device serial number: DMPT45YDG5W3
FDT: CPU 0 is not alive, disabling...
FDT: Reserving stack for CPU 1 0x806e2c000
FDT: Reserving EL3 stack for CPU 1 0x806e40000
FDT: DT CPU 1 MPIDR mismatch: 0x100000003 != 0x1
Failed to prepare FDT!
No valid payload found
```

Every payload component parsed correctly (bootargs, DTB matched to
`apple,j81`, kernel decompressed, initramfs decompressed and recognized).
m1n1 brought up **both secondary CPU cores** (`Starting CPU 1`, `Starting
CPU 2`, both `Started.`), ran a CPU vulnerability check, and began preparing
the FDT to hand off to Linux -- reporting this exact device's real serial
number (`DMPT45YDG5W3`) along the way. It failed on the very last
pre-handoff step: validating each started CPU's real MPIDR against what the
device tree declares.

Root cause, from `src/kboot.c`'s `dt_set_cpus()`: for each `cpu@N` node it
reads the `reg` property with `fdt64_ld()` -- an 8-byte load -- then compares
it against the CPU's real hardware MPIDR (`smp_get_mpidr()`), aborting on a
mismatch. The historical (2022) device tree declares `/cpus` with
`#address-cells = <1>`, so `reg` is a single 4-byte cell (`reg = <0x01>` for
`cpu@1`); `fdt64_ld()` reading 8 bytes from a 4-byte property over-reads
into whatever DTB data follows, producing the corrupted "expected" value
`0x100000003` printed above. Confirmed by decompiling both DTBs: mainline
Linux's *current* `t7001.dtsi` already uses the binding's correct
`#address-cells = <2>` (`reg = <0x0 0x1>`) -- this was never fixed
retroactively in the 2022 branch, but is already right upstream. This is
also why the "real" MPIDR value in the mismatch message, `0x1`, is the
simple, expected one -- it's the *DT-declared* side that was corrupted, not
the hardware.

**Fix**: package the *modern* kernel's `t7001-j81.dtb` (mainline-sourced,
correct 2-cell CPU `reg` format) instead of the historical kernel's own
bundled one, while keeping the historical kernel *Image* unchanged (see
`flake.nix`'s `m1n1-control` package). DTBs are meant to be decoupled from
a specific kernel build; pairing an older kernel with a structurally
corrected DTB isn't reproducing a working 2022 image byte-for-byte (this
route was already labeled a new experiment, not a control), it's fixing a
bug the 2022 DTB always had that nobody had hardware to catch before.
Verified: the repackaged `t7001-j81.dtb` now decompiles to
`#address-cells = <0x02>` / `reg = <0x00 0x00>`, `<0x00 0x01>`,
`<0x00 0x02>`.

**Attempt 3** (CPU-topology fix only, same DFU session): payload uploaded
(12,594,482 bytes), `bootm` sent, PongoOS disconnected with a timeout (not
the I/O error attempt 1 saw). **The screen went completely black**, and
`05ac:4141` no longer answers on USB at all -- a third, distinct
post-attempt signature (different from "still enumerated" and different
from "the PongoOS logo just stays there").

This is genuinely ambiguous, and it is important to be honest about that
rather than read it either way. Two things point toward this possibly being
progress, not a regression:

- `dt_set_fb()` failing to find `/chosen/framebuffer` (attempt 2's result,
  before this round's second fix) is **non-fatal in m1n1** -- it prints
  "No framebuffer found" and continues (`return 0`), it does not abort the
  boot. So even attempt 2, which never got to try the fb-node fix, could in
  principle have proceeded all the way into `kboot_boot(kernel)` with no
  framebuffer wired -- meaning "black screen" was already a possible
  *headless success* signature before this round's second fix, not
  necessarily a new failure mode introduced by fixing the CPU check.
- A real Linux kernel taking over the DWC2 USB controller for its own
  purposes (whatever the historical debug initramfs configures, if
  anything) would very plausibly no longer present PongoOS/m1n1's specific
  `05ac:4141` vendor descriptor -- "gone from the bus" is *consistent with*
  a kernel now running and owning the hardware differently, not only with a
  hard crash.

But it is equally consistent with a crash somewhere past the CPU/FDT checks
-- inside `kboot_boot()` itself, or in Linux's own very early init before
any console (fbcon or otherwise) could bind. **There is currently no way to
tell these apart.** This is precisely the observability gap the UART/JTAG
plan (`docs/project-status.md`, "UART/JTAG procurement and setup plan")
exists to close -- a serial console would show either a kernel log or a
crash dump immediately, resolving this in seconds rather than another round
of blind DFU cycles and pattern-matching on screen color.

## Fixed the same round: the DTB's framebuffer node was also a placeholder

m1n1's `dt_set_fb()` (`src/kboot.c`) looks up the framebuffer node by the
*exact* path `/chosen/framebuffer` via `fdt_path_offset()`, which does not
do prefix/wildcard matching. The mainline DTB (already in use for the CPU
fix above) declares it as `/chosen/framebuffer@0` -- same "to be filled by
loader" placeholder pattern as the zero-sized `/memory` node this
investigation found in Step 6 of the modern-stack work, just a different
node. `dt_set_fb()` renames the node to `framebuffer@<real base>` itself
once found and overwrites `reg`/`width`/`height`/`stride`/`format` and
clears `status` -- so the fix only needs the node to *exist* at the exact
pre-rename path, not to already have correct values. Fixed in `flake.nix`'s
`m1n1-control` package by decompiling the DTB, renaming
`framebuffer@0 { ... }` to `framebuffer { ... }` with `sed`, and
recompiling -- verified the repackaged DTB has `/chosen/framebuffer` with no
unit address. Whether this fix, combined with the CPU-topology fix, was
enough to reach a real console is exactly the open question attempt 3
above could not resolve.

### Attempt 4, same round, both fixes together, recorded on video: the CPU check now passes cleanly

Re-ran with both fixes applied, this time with the whole attempt recorded on
video from the PongoOS logo onward, specifically to catch anything a still
photo might miss between frames. It did.

The CPU-topology fix worked completely -- no mismatch this time:

```
FDT: CPU 1 MPIDR=0x1 release-addr=0x803b5c258
FDT: Reserving stack for CPU 2 0x806e54000
FDT: Reserving EL3 stack for CPU 2 0x806e68000
FDT: CPU 2 MPIDR=0x2 release-addr=0x803b5c298
```

Both started CPUs now report exactly the simple, expected MPIDR values
(`0x1`, `0x2`) -- confirming the earlier diagnosis precisely: the real
hardware was never the problem, only the DTB's corrupted 1-cell `reg`
reads were.

Past that, a long run of non-fatal `FDT:`/`ADT:` "not found, ignoring"
lines for peripherals this DTB doesn't fully describe for m1n1's purposes
(AIC affinities, `cpu-map`, WLAN, Bluetooth, GPU, SEP, PCIe, keyboard --
none of these are needed for a minimal console boot), then:

```
FDT: DRAM at 0x800000000 size 0x80000000
FDT: Usable mem bounds 0x800c00000..0x87d0d6000 (0x7c4d6000)
...
Preparing to boot kernel at 0x805400000 with fdt at 0x806e7c000
Booting Linux kernel at 0x805400000 with fdt at 0x806e7c000
```

**m1n1 completed its entire boot chain and executed the jump into the
actual Linux kernel entry point.** This is the furthest point this
investigation has ever reached, by a wide margin -- every m1n1-side check
now passes cleanly.

The screen still went black, and the device still dropped off USB
entirely -- same signature as attempt 3. But the video adds a real data
point the stills couldn't: **the screen actively transitions from m1n1's
white-text log to solid black, rather than staying frozen mid-log.** A hard
crash before any display-related code ever ran would leave whatever m1n1
last painted frozen in framebuffer memory, unchanged -- nothing would have
overwritten those pixels. Something (a framebuffer driver's own clear-on-
probe behavior is the obvious candidate, since `CONFIG_FB_SIMPLE=y` and
`CONFIG_FRAMEBUFFER_CONSOLE=y` are both set in the build) actively wrote
solid black into that memory after the jump. That is evidence, not proof,
that code executed *inside* the kernel after entry, not just that the
handoff itself completed.

**Update, minutes later: it did appear.** The recording was reviewed
frame-by-frame (`ffmpeg -ss <t> -frames:v 1`) rather than relying on eyes
watching it live, and at approximately t=6.50s of the video -- roughly
0.1-0.2s after the last m1n1 log line -- the screen shows genuine Linux
kernel driver-probe output, independently confirmed directly from the
source video file:

```
[    0.xxxxxx] cpufreq-dt cpufreq-dt: failed register driver: -19
[    0.xxxxxx] sdhci: Secure Digital Host Controller Interface driver
[    0.xxxxxx] sdhci: Copyright(c) Pierre Ossman
[    0.xxxxxx] sdhci-pltfm: SDHCI platform and OF driver helper
[    0.xxxxxx] leds-trig-cpu: registered to indicate activity on CPUs
[    0.xxxxxx] usbcore: registered new interface driver usbhid
[    0.xxxxxx] usbhid: USB HID core driver
[    0.xxxxxx] cs_system_cfg: CoreSight Configuration manager initialised
[    0.xxxxxx] Driver 'optee' was unable to register with bus_type 'arm_ffa'
because the bus was not initialized
```

This is unmistakably genuine upstream Linux kernel source text (`sdhci:
Copyright(c) Pierre Ossman` is the real SDHCI subsystem's own copyright
line -- not something any other layer in this chain could produce). **Linux
booted and executed real driver initialization code on this iPad Air 2.**
This is confirmed, not inferred -- the single goal this entire multi-week
investigation has been working toward.

By t=6.60s the screen is fully black again -- the visible window was well
under half a second, consistent with the user's own description ("flashed
for a short time"). Given there is no visible panic trace (no "Kernel
panic", no register dump, no backtrace) in the captured frames, and driver
probing continuing normally right up to the last visible line, the much
more mundane explanation is that boot continued past this point and
something later (a console reconfiguration, the debug initramfs's own
`/init` doing something display-related, or simply scrolling past faster
than the camera's frame rate could catch) is responsible for the
subsequent black screen -- not necessarily a crash. This specific,
narrower question -- what happens immediately after these driver-probe
lines -- is what a UART console would resolve outright. But the primary
question this whole route was built to answer is now answered: **yes, this
software-only path boots Linux on this exact iPad Air 2.**

### Checked the last visible line specifically -- it's a dead end, not a lead

`Driver 'optee' was unable to register with bus_type 'arm_ffa' because the
bus was not initialized` is the last text visible before the screen goes
black, which raises the obvious question of whether it's causally
connected. Checked directly rather than assumed: the packaged
`t7001-j81.dtb` has **no `psci` node and no `arm_ffa`/`ffa` node anywhere**
(`dtc -I dtb -O dts ... | grep -i "psci\|ffa"` returns nothing). The
`optee` driver, when compiled in (it is, per `example.config`), always
attempts FF-A bus registration as one of its possible discovery paths
regardless of whether the DTB describes that interface -- so this message
is routine, unconditional driver-probe noise on any board without an FF-A
firmware interface wired up, not a symptom of something going wrong. It
would print at essentially this same point on nearly any boot with this
kernel config, working or not.

This also rules out a specific hypothesis worth naming since it was
tempting: ARM FF-A is often tied to PSCI-mediated power management, so a
later PSCI call hitting an unconfigured secure-firmware path was briefly
considered as a way this could cascade into a crash. It doesn't apply here
-- this DTB's CPU nodes use `enable-method = "spin-table"` (confirmed
directly in m1n1's own log: each CPU gets an explicit `release-addr`), not
PSCI, so Linux was never going to rely on PSCI/FF-A for CPU management in
this boot regardless. The `optee`/`arm_ffa` line is a coincidence of
timing, not a cause -- whatever actually happens between it and the black
screen is exactly as unknown as before, and is still what UART would
resolve.

### Software follow-up: the black screen is expected behavior from the bundled initramfs

The earlier conclusion that UART was the only useful next step was premature.
Opening the exact `debug_initrd.img` embedded in the successful payload found a
much simpler explanation that requires no additional hardware.

The payload recipe copies the pinned SoMainline image unchanged:

```sh
cp ${inputs.linuxAppleResources}/debug_initrd.img "$out/initramfs.gz"
```

The hardware-tested result can be inspected without unpacking it into the
working tree:

```sh
file result-m1n1-control/initramfs.gz
gzip -dc result-m1n1-control/initramfs.gz | bsdtar -tf -
gzip -dc result-m1n1-control/initramfs.gz | bsdtar -xOf - init
gzip -dc result-m1n1-control/initramfs.gz | bsdtar -xOf - init_functions.sh
gzip -dc result-m1n1-control/initramfs.gz | bsdtar -xOf - etc/deviceinfo
```

That inspection established all of the following:

- `/etc/deviceinfo` identifies **Sony Xperia Z5 (`sony-sumire`)**, not an
  Apple device. The archive's files are dated June 2020.
- `setup_log()` redirects PID 1's stdout and stderr to `/pmOS_init.log` unless
  `/proc/cmdline` contains `PMOS_NO_OUTPUT_REDIRECT`. The log exists only in
  RAM and is currently unreachable from the host.
- `setup_framebuffer()` waits for `/dev/fb0`; the debug-shell hook then calls
  `fbsplash` and waits forever in a shell or sleep loop.
- Both bundled splash images are 1080x1920, while the Air 2 framebuffer m1n1
  reports is 2224x1668. Their mean byte values are only 1.36 and 1.91 on a
  0-255 scale: they are more than 99% black.

This behavior matches the recorded hardware result plausibly, but **"Round
2" below found a sharper, more likely explanation and superseded this as the
leading one**: `setup_log()` prints an unconditional marker line before it
ever checks the redirect flag, and that marker has never been observed on
screen -- across any attempt, with or without `PMOS_NO_OUTPUT_REDIRECT` set.
That means PID 1 most likely never starts at all, which this specific
initramfs-behavior explanation doesn't actually predict. It's not wrong
about what the bundled initramfs does; it's likely just not what's actually
happening here. See "Round 2" for the current leading hypothesis
(power-domain auto-shutdown, inside the kernel, before `/init` runs).

There is a separate reason no host-side console appeared. The modern mainline
DTB selected to fix m1n1's CPU-property parsing has no USB-device controller
node. Decompiling the two built DTBs shows:

- `result-historical-kernel/dtbs/apple/t7001-j81.dtb` contains
  `usbdev@20c100000`, compatible with `apple,t7000-usb`.
- `result-m1n1-control/t7001-j81.dtb` contains USB power domains but no USB
  controller. The historical kernel includes a matching Apple DWC2 driver;
  without the DT node it can never create a UDC for the initramfs.

The current Hoolock tree reaches the same conclusion from the other direction:
its T7001 DT describes the USB complex, PHY and peripheral-mode DWC2 controller,
and its test ramdisk exposes a framebuffer shell plus USB network and ACM
serial consoles. See [Hoolock's setup guide](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP.md),
[A8/A8X feature matrix](https://github.com/HoolockLinux/docs/blob/master/features/A8.md),
and [HoolockRD](https://github.com/HoolockLinux/HoolockRD).

#### Next tests, in order

Change one layer at a time and stop at the first test that provides a stable
console:

1. Keep the hardware-proven PongoOS, m1n1, DTB, kernel and initramfs. Change
   only the bootargs to:

   ```text
   chosen.bootargs=console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT
   ```

   Success is visible postmarketOS PID 1 output after the kernel messages.
2. If the splash still obscures the console, replace only the initramfs with a
   tiny BusyBox `/init` that mounts `/proc`, `/sys` and `/dev`, repeatedly
   prints an unmistakable `PID 1 ALIVE` marker to `/dev/console`, and never
   exits. Do not add SSH, networking or storage to this diagnostic.
3. Restore the historical DTB and patch only the two defects already confirmed
   on hardware: convert the CPU `reg` values to two cells for m1n1, and add the
   exact `/chosen/framebuffer` placeholder m1n1 expects. This preserves the
   historical USB node and its matched kernel driver.
4. After PID 1 is visible, test host enumeration over the existing Lightning
   cable. If the historical RNDIS-only userspace is unsuitable on macOS, move
   the whole kernel/DTB/initramfs set together to a pinned Hoolock kernel plus
   HoolockRD, which provides USB ACM serial and NCM/RNDIS networking.
5. Only after a stable visible or USB shell exists, substitute this project's
   NixOS initramfs and diagnose its services one at a time.

UART remains a useful fallback if both framebuffer and the matched USB-device
path fail, but it is no longer a prerequisite or the next recommended expense.

### Round 2, 2026-09-07: step 1 alone was insufficient, and a sharper hypothesis

Implemented step 1 (`PMOS_NO_OUTPUT_REDIRECT` added to bootargs) and ran it
on hardware, twice -- once on ordinary video, once at 120fps specifically to
catch anything sub-frame. Both times: still black, still off USB. But the
120fps capture showed noticeably more kernel driver-probe text than any
previous attempt (PPP, EHCI, Bluetooth HCI UART, `i2c_dev`, device-mapper,
per-CPU `cpufreq_init` failures, `sdhci`, `ledtrig-cpu`) before the same
abrupt cutoff to black, within roughly 40ms in the frame-by-frame check.

That extra detail pointed at something the original "hidden Xperia splash"
theory didn't actually predict, once checked carefully: `setup_log()`
(`init_functions.sh`) prints `### postmarketOS initramfs ###`
**unconditionally, before it even checks the redirect flag** -- so if PID 1
had ever actually started, that exact string should be visible on screen
regardless of whether `PMOS_NO_OUTPUT_REDIRECT` is set. It has never
appeared, in any frame, across any attempt. That means the leading
explanation from the first round was checking the right file but drawing
the wrong conclusion about whether we ever reach it -- PID 1 most likely
never starts. Whatever stops output does so **inside the kernel itself**,
after driver probing, before `/init` ever runs.

A concrete, well-targeted candidate for what that is: Apple's PMGR power-
domain driver (`drivers/soc/apple/apple-pmgr-pwrstate.c`, in the historical
kernel source) implements the generic power-domain (genpd) framework.
`drivers/base/power/domain.c`'s `genpd_power_off_unused()` runs as a
`late_initcall()` -- exactly the point right after the device-probing this
project has now watched complete, on video, more than once -- and powers
off any power domain with no active consumer. Checked directly: the
packaged DTB's `/chosen/framebuffer` node declares
`power-domains = <0x18 0x1d>`, and those two phandles resolve to power
controllers labeled `disp0` and `dp` -- the display controller and
display-port domains, precisely what the inherited framebuffer depends on
and precisely the kind of thing with no explicit Linux consumer holding it
open (there is no real display driver here, just an inherited simplefb
framebuffer). If the generic `simple-framebuffer` platform driver doesn't
itself hold a runtime-PM reference on those domains, `genpd_power_off_unused()`
turning them off would explain the observed behavior exactly: driver
probing finishes, then shortly after, the screen goes dark, and (since PID 1
never gets to run) nothing further is ever printed anywhere.

**Fix, added to bootargs alongside the existing ones**: `pd_ignore_unused`
and `clk_ignore_unused` -- real, standard kernel parameters
(`drivers/base/power/domain.c`, `drivers/clk/clk.c`, both confirmed present
in the historical kernel source) that disable exactly this automatic
unused-resource shutdown. Not yet run on hardware.

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
