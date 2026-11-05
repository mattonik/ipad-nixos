# J81 GPU test batch: preparation

2026-11-04. This is a staged diagnostic, not a GPU driver. The first PMGR
observation was run as recorded below. Do not execute a stage until its capture, ownership and
recovery requirements in `research/2026-11-04-j81-gpu-diagnostic-recovery.md`
have been reviewed.

## Orchard comparison

OrchardLinux/gpu `main` was checked at commit
[`42f6add03616d065d137e60c2cd7fde8780e5203`](https://github.com/OrchardLinux/gpu/commit/42f6add03616d065d137e60c2cd7fde8780e5203)
on 2026-11-04. Its [A10 README](https://github.com/OrchardLinux/gpu/blob/42f6add03616d065d137e60c2cd7fde8780e5203/a10/README.md)
reports accelerated desktop rendering on J71b. The driver depends on A10's
GFX coprocessor and RTKit, whereas J81's 8.1 code and firmware use META; it
is not an A8X driver. Its [power notes](https://github.com/OrchardLinux/gpu/blob/42f6add03616d065d137e60c2cd7fde8780e5203/a10/bringup/power-display.md)
identify Fender `+0x1000` as the A10 performance-state request and report a
silent reset caused by a state-0 ordering error. Our own 8.1 G4G trace
independently finds a similar register and bit, but A10's state count,
timing, RTKit setup and fastest-state defaults are not validated for J81.

## Stage 0: control and inventory

The previously completed control boot is documented in the recovery note:
Linux's simple-framebuffer is the only DRM device, and the PMGR power-domain
platform driver binds. The control root is RAM-backed and no internal-storage
mount was observed. This inventory does not read the GFX power register and
cannot say whether the GPU is actually powered.

## Stage 1: one PMGR state observation

`boot/gpu-pmgr-peek.c` opens `/dev/mem` read-only, maps the fixed PMGR page
read-only, prints and flushes a stage marker, waits for the host's `READ`
acknowledgement, reads exactly one 32-bit word at physical `0x20e020320`,
and prints the raw word and target, actual, auto,
and reset fields. The address is the GFX PMGR state register independently
identified from both J81 ADTs and the 8.1 controller code. It never maps or
accesses the GPU core or Fender and does not write a register. A physical
MMIO read can still hang or fault; read-only does not guarantee safe recovery.
The software fields do not prove that the GPU is clocked or safe to access.

Build on the documented Linux builder and run the host-only fake-memory test:

```sh
tools/builder.sh status
tools/builder.sh build --who j81-gpu '.#packages.x86_64-linux.gpu-pmgr-peek-static' -o artifacts/live/gcroot-gpu-pmgr-peek
/opt/homebrew/bin/python3 boot/test_gpu_pmgr_peek.py
/opt/homebrew/bin/python3 boot/test_gpu_pmgr_capture.py
shasum -a 256 artifacts/live/gcroot-gpu-pmgr-peek/bin/gpu-pmgr-peek
```

The 2026-11-04 build is a statically linked AArch64 ELF with SHA-256
`78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd`.
The host test exercises the fixed read-only mapping, argument rejection,
open/mmap failure, acknowledgement rejection, and decoding against a fake
memory page. A socket-pair test checks that the collector persists the marker
before acknowledging and rejects incomplete or stale completion. These do not
test real hardware, `/dev/mem` permission, telnet transport, the selected
kernel or bus behavior; the later run below is separate evidence.

`boot/gpu_pmgr_capture.py` is a dedicated live collector for this one
stage: after it has written and fsynced the marker to a new private host log,
it sends `READ` and waits for the result. The existing
`boot/ipad_telnet_run.py` buffers output until completion and must not be used
as this collector. The handshake and transport were exercised in the run
below; the binary must first be staged at `/tmp/gpu-pmgr-peek` on the intended
control boot and checked against the approved hash. No unattended run or
automatic recovery is established. Confirm operator availability and the
device's recovery path before any eventual MMIO read.

## Later stages

A managed, bounded power-and-Fender test and an identity read require separate
implementation and review. They must establish domain ownership, check each
return, preserve raw values, use timeouts, avoid an unproven power-off or
rollback after failure, and handle the possibility that one MMIO access never
returns. A GPU firmware upload or workload is outside this first batch. The
existing G4G LDR findings suggest a related firmware container, not an already
compatible Linux firmware ABI.

### Offline LDR inspector

`tools/gpu_ldr_inspect.py` checks the known META LDR record chain and prints
aggregate counts without extracting or displaying firmware. Run it directly
against the private kernelcaches (which must remain under `artifacts/`):

```sh
python3 tools/gpu_ldr_inspect.py artifacts/live/private/gpu-offline/kernelcache --offset 0xdd0327 --size 0x16cd8
python3 tools/gpu_ldr_inspect.py artifacts/live/private/gpu-offline/ios15-kernel --offset 0xe579c8 --size 0x1cbb4
python3 tools/test_gpu_ldr_inspect.py
```

For the previously identified images, the iOS 8.1 span has 80 records,
including 58 loads, 14 zeroes and two configuration records; the iPadOS 15
span has 88 records, including 67 loads, 13 zeroes and two configuration
records. Both have one start record with two thread entries and 27
configuration writes. The inspector checks chain and payload bounds,
supported command shapes and address wraparound. It does not verify CRCs,
target address safety or overlap, firmware authenticity, thread semantics,
or compatibility with the Linux PowerVR host protocol. Passing it is not
permission or sufficient evidence to upload or run firmware.

The standard Linux platform-device probe path attaches and powers its domain
before invoking the driver's probe. A diagnostic that waits until its probe to
emit a host checkpoint would therefore miss the transition. The explicit
`of_genpd_add_device()` path appears to separate attachment from power-on,
but its lifetime, failure and recovery behavior needs a reviewed design and
build before a managed power test can use it. No such power test or GPU
identity-read implementation is provided by the inspector.

### PMGR failure handling candidate

Source review found that the pinned `apple_pmgr_ps_set()` ignores both
`regmap_write()` return values and, after a failed state poll, still writes
the automatic-power-enable bit. The isolated candidate
`kernel/patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch` checks both
writes and returns immediately on a failed poll. For the test-only J81 GFX
property it also refuses PMGR power-off requests, and exports a marker the
test module requires. The changes affect the shared PMGR driver and must be
reviewed as such. They are not part of the known-good control payload.

The actual patched function can be exercised with fake regmap operations:

```sh
python3 kernel/test_gpu_pmgr_failure_patch.py --source artifacts/live/private/gpu-offline/pmgr-pwrstate.c
```

The source file is a local copy of the pinned builder's PMGR driver. The test
applies the patch with zero fuzz, compiles the function with a fake regmap,
and tests initial-read failure, first-write failure, poll timeout,
automatic-enable write failure and normal on/off calls. This does not model
actual electrical effects, concurrent users, a stuck bus, or Linux genpd's
complete hierarchy and rollback. In particular, generic genpd can power down
parent domains while unwinding a failed power-on, and can request a power-off
after a later runtime-resume callback fails. These paths must be resolved for
the actual J81 domain before a managed diagnostic can safely rely on them.
Even with the patch, an error can leave hardware in an unknown state.
For example, the auto-enable write can fail after the domain reached the
active state, while genpd still treats the power-on operation as failed.

The currently running control boot's device tree lists GFX with no
`power-domains` property, so it declares no parent domain for genpd to unwind.
This observation applies only to that boot's tree, not to future payloads.
The pinned genpd implementation also returns `-EPROBE_DEFER` when a
platform-device attachment's power-on fails. That can cause the driver core
to retry the probe: simply emitting a host checkpoint before loading a
normal platform driver does not make that path a one-shot test. A diagnostic
must avoid or explicitly eliminate that automatic retry and must check its
actual device tree and runtime callbacks.

### Power-only prototype, not ready to run

`kernel/gpu-pmgr-once/` is an experimental module that uses
`of_genpd_add_device()` on a standalone root device instead of platform
probe, so attachment and a single explicit runtime-PM power request are
separate. The module refuses an unexpected machine, GFX node, parent domain,
register range or missing test-only no-power-off property. It requires the
exported marker from the patched PMGR driver. After the host authorizes the
single request, it re-reads the PMGR word and accepts only the previously
observed `0x00000300` before calling `pm_runtime_get_sync()`. If it calls
runtime-PM, it retains that reference on success or failure. It has no unload path;
the test boot must end in a physical restart. It never accesses the GPC or
GPU core and cannot read the GPU ID or render.

Before obtaining the PMGR regmap, the module also checks that the existing
`apple-pmgr-pwrstate` provider is bound; otherwise a syscon lookup could
instantiate resources before the checkpoint. This assumes no concurrent
administrator is unbinding or changing the PMGR provider during the test.
The source audit fingerprints the exact pinned files and checks relevant
attachment, provider and runtime-PM assumptions; it does not prove that the
running kernel matches those sources.

`boot/gpu-pmgr-once-run.sh` verifies the module, kernel-notes and established
PMGR-reader hashes, attaches the module or validates the already-loaded
module's build-ID note, then runs the read-only PMGR reader. Reusing a loaded
module is restricted to the exact tested module-file hash and build-ID note;
the build ID is identification, not cryptographic proof of all loaded code.
`boot/gpu_power_capture.py` persists and acknowledges that read, checks the
raw starting state, and separately persists and acknowledges the power
checkpoint. Error, unexpected state, stale completion, disconnect and timeout
stop the sequence. Each PMGR operation inside the kernel's power-on callback
is not individually host-acknowledged; the power checkpoint covers the whole
transition. A single stuck MMIO operation cannot be interrupted by a host
deadline. The isolated patch's no-power-off guard applies to the PMGR callback,
not arbitrary code that writes its registers directly.

The actual module and patched PMGR function have host mock tests, and the
wrapper and collector have simulated-failure tests. These do not establish
that power-up is electrically safe or physical recovery works. A matching
test kernel, module, boot payload, exact kernel-notes hash, and staging and
review procedure must all be verified before considering a live run. Do not
load a module compiled against a different kernel, infer ownership solely
from the PMGR word, or use these files to run an unattended test.

For reproducible builds from the repository root (no boot or device access):

```sh
tools/builder.sh build --who gpu-pmgr --impure -o artifacts/live/gcroot-gpu-pmgr-once-kernel --expr '(import ./kernel/gpu-pmgr-once/build.nix { repo = builtins.toPath (builtins.getEnv "PWD"); }).kernel'
tools/builder.sh build --who gpu-pmgr --impure -o artifacts/live/gcroot-gpu-pmgr-once-kernel --expr '(import ./kernel/gpu-pmgr-once/build.nix { repo = builtins.toPath (builtins.getEnv "PWD"); }).kernel.dev'
tools/builder.sh build --who gpu-pmgr --impure -o artifacts/live/gcroot-gpu-pmgr-once-module --expr '(import ./kernel/gpu-pmgr-once/build.nix { repo = builtins.toPath (builtins.getEnv "PWD"); }).module'
tools/builder.sh build --who gpu-pmgr --impure -o artifacts/live/gcroot-gpu-pmgr-once-payload --expr '(import ./kernel/gpu-pmgr-once/build.nix { repo = builtins.toPath (builtins.getEnv "PWD"); }).payload'
python3 kernel/audit_gpu_genpd_source.py artifacts/live/private/gpu-offline/linux-src
python3 boot/verify_gpu_pmgr_payload.py artifacts/live/gcroot-gpu-pmgr-once-payload artifacts/live/gcroot-clean-production artifacts/live/gcroot-gpu-pmgr-once-kernel
python3 boot/kernel_notes_sha256.py artifacts/live/gcroot-gpu-pmgr-once-kernel-dev/vmlinux
```

The module derivation builds against the same patched kernel's development
output; the payload combines that kernel and its device tree with the exact
known-good control's Pongo, m1n1, boot arguments and initramfs. Use
`boot/verify_gpu_pmgr_payload.py` with the test
payload, the known-good control directory and the test kernel output to
compare their components and check the test device tree. The expected kernel
notes hash can be calculated from the matching development output's `vmlinux`
with `boot/kernel_notes_sha256.py`. Its ELF section extraction was compared
with GNU objcopy on an existing AArch64 kernel; equality with the test boot's
`/sys/kernel/notes` still requires verification. A completed build is not
itself a live-test gate.

Build result, 2026-11-04:

| Artifact | SHA-256 |
| --- | --- |
| Test kernel `Image` | `f5513a7bd7bf1b363b5c0bfbc5a81785de31c2ad570553bbc39ba65ee20ab1ae` |
| Test `gpu-pmgr-once.ko` | `39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89` |
| Test `m1n1-linux.bin` | `06fba59c175dee48e6532257bf3e4c954650b1d3149d7aefbd856809a5ec08c1` |
| Expected kernel `.notes` | `82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014` |

The payload verifier passed against the saved control. The built AArch64
module has an undefined reference to `j81_gpu_pmgr_failstop_v1`, which is
exported by the matching test kernel; it has no `cleanup_module` symbol or
automatic-load alias. GNU objcopy independently produced the same `.notes`
hash as the Python extractor. The subsequent boot and attachment are recorded
below. The GFX transition and recovery after a GPU hang remain untested.

On the still-running control boot, a read-only check found neither the
test-only symbol in `/proc/kallsyms` nor the GFX test property in its device
tree. Its `/sys/kernel/notes` SHA-256 was
`7933908f2a1ede1ab65c3c2ae35a00de2a14bc63b7bfed30d8aaad3232a1768f`,
different from the expected test-kernel notes. This supports rejection of
the current boot by the test's gates; the module was not loaded to test that
rejection.

### Test-kernel boot and inert attachment: 2026-11-05

After the user placed the iPad in DFU, checkm8 reached PongoOS and the
verified test payload above was uploaded to RAM. The USB shell returned and
`/sys/kernel/notes` hashed to the expected
`82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`.
The test-only GFX device-tree property was present, the PMGR provider was
bound, root was `rootfs`, and the observed mount list contained no internal
storage mount. The user reported the test dashboard on the iPad.

Before loading the module, the existing separately acknowledged read-only
PMGR diagnostic returned `0x00000300`; Linux debugfs reported GFX `off-0`
with no listed consumers or children. The exact built module was then staged
in `/tmp`, its SHA-256 verified, and loaded **without writing its power
attribute**. Linux reported GFX `off-0` with `gpu-pmgr-once` suspended. A
second separately acknowledged PMGR read remained `0x00000300`. Writing the
invalid values `0`, `2`, and `invalid` to the attribute was rejected, GFX remained reported off,
and the network responded. The two PMGR captures remain private under
`artifacts/live/private/gpu-observations/`.

This verifies a test-kernel boot and this module's inert attachment on one
boot. No valid power request, GPC/GPU access, firmware execution or workload
was made. The current module intentionally cannot unload. Its loaded build-ID
note matched the independently extracted note from the exact module file.
A subsequent live dry run reused the loaded module, repeated the acknowledged
PMGR read, saved the before-power marker, and substituted `NO` for `POWER`;
no power request was sent. This avoids another DFU for a future power test
while this boot and module remain intact. Physical restart after a GPU hang
has not been tested, and these results do not establish electrical safety of
power-on. The dry-run capture is private under
`artifacts/live/private/gpu-observations/`.

### GFX power-only result: 2026-11-05

On a fresh boot of the verified test payload, the user requested tests. The
kernel notes and staged module, wrapper and reader hashes matched the reviewed
artifacts. Before the test, Linux reported GFX `off-0` with no listed
consumer, the diagnostic was not loaded, and the root was `rootfs`.

The dedicated host collector saved and acknowledged the PMGR read marker,
received `0x00000300` (target 0, actual 0, auto 0, reset 0), and saved and
acknowledged the power marker. The one-shot request returned `rc=0`. Linux
then reported GFX `on` with `gpu-pmgr-once` active and runtime usage count 1.
A separately acknowledged read of the PMGR word returned `0x000003ff`
(target 15, actual 15, auto 0, reset 0). Thus the auto-enable bit did not
read back as set on this observation; its hardware meaning is not assumed.
The iPad remained responsive. A second valid request was rejected by the
one-shot guard, with the domain still reported on and usage count 1.

The power and post-power read captures are private under
`artifacts/live/private/gpu-observations/`. This establishes one successful
power-domain transition and guard rejection on this boot; it does not prove
GPC initialization, GPU register accessibility, firmware compatibility,
rendering, long-term thermal behavior, or restart after a GPU hang. The
module intentionally remains loaded with its power reference until reboot;
no GPC or GPU-core register was accessed and no firmware was executed.

A later separately acknowledged read, about three minutes after the
transition, again returned `0x000003ff`; Linux still reported the domain on,
the diagnostic runtime-active and usage count 1. The network shell remained
responsive. `/dev/dri` still exposed only `card0`, bound to
`simple-framebuffer`, so this power transition has not produced a GPU render
node. The available `thermal_zone0` identified itself as the bq27545 battery
sensor; its reading is not evidence of GPU die temperature. The later PMGR
capture is private under `artifacts/live/private/gpu-observations/`.

## Stage 1 result: 2026-11-04

On the already-running verified control boot, the user authorized tests on
the iPad. The PMGR driver was already bound to `power-controller@20320`;
its probe reads the same state word through regmap. The test binary was
copied into RAM at `/tmp/gpu-pmgr-peek` and its SHA-256 matched the build
above. An invalid-argument check exited 2; a `NO` handshake exited 1 after
the pre-read marker without reading the register. Both checks left the
system responsive.

The live host collector then saved the pre-read marker and acknowledged the
single read. It recorded:

```text
raw=0x00000300 target=0 actual=0 auto=0 reset=0
```

The iPad responded to ping and the shell afterward. This is one observation
on this control boot: the PMGR fields report target and actual state 0 and
bits 8 and 9 set; Linux labels those bits `WAS_PWRGATED` and
`WAS_CLKGATED`. It does not reveal when those indications arose, prove the
entire GPU is safe to touch, or establish recovery from a hang. No power
transition, Fender or GPU-core register access, firmware upload, or GPU
workload occurred. The raw host capture remains private under
`artifacts/live/private/gpu-observations/`.


### Clock prerequisite discovered: 2026-11-05

On the same test boot, read-only Linux status confirmed the expected
kernel notes, GFX `on`, and the test consumer `active`; the shell remained
responsive and `/dev/dri` still contained only `card0`. Further offline
tracing found that the iOS GFX clock-enable path can apply two 33-entry
bridge register tables before its GPC and GPU ID probe. Whether this boot
has equivalent settings is unknown; see the offline trace. The planned
GPC diagnostic was not built or run pending that prerequisite. No bridge,
GPC, or GPU-core register was accessed in this follow-up.


### GPC observation prototype: 2026-11-05

Prepared a read-only, one-shot GPC observer and host checkpoint capture.
The intended first access is GPC `+0x1000`; only if its low five bits
are `1` does the observer offer a separate checkpoint for GPC `+0`.
Each access requires an independent host acknowledgement after its
marker is flushed to a private, fsynced host log. The host independently
rejects an unexpected PMGR word, an unsettled or non-1 GPC state,
out-of-order stages, or an incomplete capture. The wrapper checks the
known test-kernel notes, loaded diagnostic build ID, active usage count,
RAM root, PMGR-reader hash and observer hash. The observer cannot write
MMIO or access the GPU core, and its guard prevents a second attempt in
the same boot even after failure. These checks do not make an unknown
MMIO read safe and do not prevent a hung transaction.

Built the static AArch64 observer under
`artifacts/live/gcroot-gpu-gpc-peek/bin/gpu-gpc-peek`, SHA-256
`ed83b0581371f641363018d9d28044fe4adb8fa905d9823de3fd1e8cbe204564`.
Host-only fake-mapping and socket tests passed, including refusing a
second read on an unsuitable state and a result sent before its
checkpoint. The build and tests do not validate the actual GPC access.
The wrapper, collector and binary have not been staged or run on the
iPad. Live use remains blocked by unproven bridge/read behavior and
recovery from a bus hang; the neighboring A8 report is not a J81
safety qualification. No GPC initialization or GPU ID read occurred.


### GPC observer inert device verification: 2026-11-05

The observer binary was staged in RAM on the still-responsive verified
test boot. Its SHA-256 matched the offline build
`ed83b0581371f641363018d9d28044fe4adb8fa905d9823de3fd1e8cbe204564`.
Invoking it with an extra argument returned exit 2, before its one-shot
guard, `/dev/mem` open or MMIO mapping; the guard remained absent.
The wrapper SHA-256 was
`376c70be7c10ad96ee945c1b8f6fe3900e7d5738ee3919eac58cc6428fa9b49a`.
A live preflight dry run passed kernel, module, usage, RAM-root and
no-`/dev/`-mount checks, emitted the PMGR pre-read checkpoint, received
`NO`, and exited 1. The GPC observer did not start, its one-shot guard
remained absent, and no PMGR or GPC MMIO read was authorized in that
dry run. The wrapper now refuses block-device-backed mounts; its fake
device-tree test covers that refusal. These are inert checks only, not a
qualification of the GPC mapping, its registers or physical recovery.


### GPC mapping without an MMIO transaction: 2026-11-05

A separately built observer adds `--map-only`, which opens `/dev/mem`
read-only, maps the GPC region, immediately unmaps it and exits without
loading from the mapping. This mode does not create the read observer's
one-shot guard. The fake-mapping test verifies the mode takes no read
acknowledgements and does not consume that guard. Its static AArch64
binary, SHA-256
`2c6e4bce8fd900899b86dfc138e778e053b76f1d48132c976d3b9153edb0ea5c`,
was staged separately as `/tmp/gpu-gpc-map-only`. On the test boot it
reported `stage=gpc-mapped-no-access`, exited 0 and left the one-shot
guard absent; the shell remained responsive. This verifies the kernel
accepted that mapping, not that the hardware will respond to any MMIO
read or write. No GPC or GPU-core register was read. The earlier
`/tmp/gpu-gpc-peek` remains the previous verified observer build.


The map-only host test was strengthened by returning an intentionally
invalid pointer as the fake mapping; the map-only path completes without
dereferencing it. A later read-only system check found the iPad responsive,
the GFX consumer still active, and no one-shot guard. The recent kernel
log contained no new entry after the earlier diagnostic module load; this
is not proof of GPC accessibility or of long-term hardware health.


### First GPC state observation: 2026-11-05

With the user's go-ahead, the verified RAM boot, staged observer and
wrapper hashes, one-shot guard and runtime usage were checked. The host
collector persisted each checkpoint before acknowledging the read.
The PMGR word again returned `0x000003ff` (target and actual 15). The
single subsequent read of GPC `0x201e01000` returned `0x00000000`. Its
low five bits are not 1, so both observer and host refused the next
GPC-control read; the collector reported its expected stop as an error.
The one-shot guard is present, Linux still reports the consumer active
and the iPad remained responsive. The private host log is
`artifacts/live/private/gpu-observations/2026-11-05-gpc-observe-01.log`.

This is one successful GPC state-register access with PMGR on; it is
not a GPC power transition, GPU identity read, or proof that the RGX
block is accessible. The zero means the sampled low state nibble and
transition bit are zero, not that the entire GPU is electrically off.
No GPC control register, bridge register or GPU-core register was read
or written. Do not retry this one-shot in the same boot.


### GPC state-1 initialization prototype: 2026-11-05

Prepared `boot/gpu-gpc-init.c`, its host capture and identity-gating
wrapper. The one-shot program demands a newly sampled initial GPC state
word of exactly zero, and then offers three separately acknowledged
writes matching the 8.1 Apple probe: `+0x10000=0xffff0000`,
`+0=0x40000000`, and `+0x1000=0x11`. It offers separately acknowledged
state reads, up to 64, stops on cleared transition bit, and reports
success only for state 1. It does not access RGX or attempt a rollback
on failure. A host fsyncs stage markers before each acknowledgement
and independently checks the PMGR word, operation order, values,
initial state, poll limit and final result. A completed store marker is
not proof that hardware finished the requested transition.

The static AArch64 binary SHA-256 is
`8a67ba955fca1aa2fe2b043e4512919aefa49c475542af1581d32b388f988282`;
the wrapper SHA-256 is
`de1ec4dfdd741c85d948779e4642e50b7aa6232a890be9745982e6a67cfac17f`.
Both were staged in RAM, hash checked, and exercised only on inert
paths: an invalid binary argument exited before opening MMIO, and
the wrapper's PMGR pre-read checkpoint was refused with `NO`. The init
one-shot guard was not created. Host-only mocked MMIO and socket tests
cover ordered operations, invalid starting state, refused acknowledgements,
poll limits, unexpected final states and missing completion. The iPad
remained responsive.

No initialization write was made. Apple calls its clock/power path before
these GPC accesses, which can include bridge writes; we have not verified
that equivalent bridge setup is present on this boot, the safe behavior
of each GPC write in its absence, or physical recovery after a hang.
The prototype therefore is not approved as electrically safe by these
software checks. The neighboring A8 result is encouraging only for
GPC access and does not establish J81 write safety or RGX accessibility.


### First GPC state-1 request: 2026-11-05

On the verified RAM test boot, after the user's instruction to proceed,
the staged binary and wrapper hashes, active PMGR consumer, runtime usage
and absent init one-shot guard were verified. The host persisted and
acknowledged each operation's checkpoint. The PMGR word read `0x000003ff`
and the GPC initial state read `0x00000000`. The diagnostic then wrote
`0xffff0000` to GPC `+0x10000`, `0x40000000` to `+0`, and `0x11` to
`+0x1000`. The first bounded status poll read `0x00000001`; the program
reported `stage=finished rc=0`. The raw host capture is
`artifacts/live/private/gpu-observations/2026-11-05-gpc-init-01.log`.

The iPad stayed responsive, Linux reported GFX on with runtime usage 1,
and the initialization one-shot guard is present. The after-write markers
are software completion markers, not independent readback of the written
values; the separate poll is the state observation. This is one state-1
request and status read on this boot, not evidence that RGX registers are
accessible, a verified clock/bridge setup, firmware execution, rendering,
or safe recovery or power-down. No RGX or bridge register was read or
written. The diagnostic deliberately left the state and PMGR reference
as found after the request and must not be retried in this boot.


### First guarded GPU revision read: 2026-11-05

Following the user's request to try, a one-shot read-only GPU ID
observer and independent host collector were built. The binary and
wrapper hashes were verified, and the inert argument and refused-PMGR
preflight paths passed on the RAM boot. Host-only simulated tests passed
for state and power-down-handshake gates, rejected acknowledgements,
order and incomplete capture. Offline suite: 63 passed, 7 skipped.

The host-persisted capture reported PMGR `0x000003ff`, GPC state
`0x00000001`, and GPC control `0x40000000` (bit 29 clear). It then
persisted the checkpoint for a single 32-bit GPU revision read at
`0x201000020` and acknowledged it. No after-read result arrived before
the 30-second deadline. The collector stopped with an incomplete-capture
error; device state is unknown. No `+0x18` core-ID read was attempted.
The private raw log is
`artifacts/live/private/gpu-observations/2026-11-05-gpu-id-01.log`.

The last checkpoint is consistent with a stuck first RGX read, as seen
in the separately reported J96 experiment, but host silence alone does
not independently prove the cause. No retry, automatic power-off,
unbind, reset, or further device command was issued. Physical force
restart via Home + top and confirmation of the Apple logo remain the
recovery attempt; no successful recovery has yet been observed.


### Recovery after the revision-read timeout: 2026-11-05

The user reported that the iPad restarted and they placed it back into
DFU. The host subsequently observed Apple USB product `0x1227`,
consistent with DFU. This establishes a responsive DFU USB identity
after the failed revision-read attempt; it does not independently
confirm that the stock OS booted or that the Apple logo appeared.
No second GPU read or GPC access was attempted. The previously booted
RAM control payload's `m1n1-linux.bin` again matched SHA-256
`b3206c51c096d9e0cb47473cdcd88157acf677388805eb3532df071ce7315781`.
Starting the control boot remained blocked because `sudo -n` reported
that the Mac requires authentication. The control payload is not a
private-manifest payload; the private-payload launcher cannot verify it
as one.


### Bridge experiment preparation and control-boot preflight: 2026-11-05

The user subsequently reported a successful stock iOS boot before
returning the iPad to DFU. A known-good RAM control image was then
booted; its kernel notes SHA-256 is
`7933908f2a1ede1ab65c3c2ae35a00de2a14bc63b7bfed30d8aaad3232a1768f`.
This supersedes the earlier statement that a stock boot was unconfirmed.

A bridge experiment prototype was built and tested without executing
bridge MMIO. It checks a private 66-entry plan, requires an initial GPC
state of zero and a host-persisted acknowledgement for every operation.
The host collector verifies the expected order and stops on missing or
unexpected checkpoints. Write completion markers are software markers,
not independent hardware readback. The private plan SHA-256 is
`1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435`;
its values remain outside Git.

The static ARM64 binary SHA-256 is
`3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c`.
On the running control boot, staged files matched their expected hashes;
the binary rejected an invalid argument, and the wrapper rejected the
control kernel before the PMGR observer or bridge program ran. The
one-shot guard remained absent and the iPad remained responsive.
Simulated MMIO and collector tests cover the ordered sequence and
failure paths; the offline suite passed 66 checks with 7 skipped.

The bridge tables are a candidate missing setup, not an established
explanation for the failed core read. Their first entry's semantics and
the effects of writing these shared fabric windows are not established.
No bridge write was attempted, and these software checks do not establish
that a live replay is safe or that it would enable the GPU.


### On-device ARM64 simulation: 2026-11-05

The same synthetic harness used for the bridge diagnostic's host tests
was compiled as a static ARM64 program and run on the responsive RAM
control boot. SHA-256 of the binary:
`411487f69f4482fa9cfcc0a13e2dfbe84fcd60eb04938e914bd65a5cda3380ba`.
Its assertions passed: invalid arguments and malformed plans stop before
the simulated access, nonzero GPC state prevents writes, a refused
acknowledgement stops mid-sequence, the one-shot guard prevents a
retry, and an accepted synthetic sequence reaches all 66 writes. The
RAM guard used by the real hardware diagnostic remained absent; the
control boot remained responsive.

The harness replaces open, read, mmap, MMIO, acknowledgements, and the
guard with in-process fakes and uses synthetic table values. This tests
ARM64 execution and software control flow only. It does not test the
real host collector, GPU bridge, display coordination, actual device
mappings or electrical safety. The program and build are in
`boot/test-gpu-bridge-sim.c` and the `gpu-bridge-sim-static` flake
package; the offline suite passed 66 checks, with 7 skipped.


### Control-boot GFX PMGR observation and overlap simulation

On the responsive control boot, kernel notes matched SHA-256
`7933908f2a1ede1ab65c3c2ae35a00de2a14bc63b7bfed30d8aaad3232a1768f`
and the previously validated PMGR observer matched SHA-256
`78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd`.
A host-persisted checkpoint preceded one read of the same PMGR state
word that was already observed on a control boot. It returned
`0x00000300` (target 0, actual 0, auto 0, reset 0). The iPad remained
responsive. This is PMGR outer-domain state, not proof of GPU core
state, bridge settings, electrical safety, or future recovery. No
power transition, GPC, bridge or GPU-core MMIO was issued. The capture
is private at `artifacts/live/private/gpu-observations/2026-11-05-control-pmgr-followup-01.log`.

The ARM64 simulation was corrected to model the declared bridge-window
overlap with a single shared fake fabric array. On the iPad, the
synthetic simulation passed its existing stop/sequence cases and
verified that selector 10's first write aliases selector 9's overlapping
mapping. Binary SHA-256:
`ba227d84c139223d46f71749d796a6f0517c142f62bea680779c5519166a5aeb`.
All accesses remained in fake RAM, and the real hardware one-shot guard
remained absent. This checks the simulation's address model, not bridge
behavior.


### On-device bridge mapping without MMIO

Built `boot/gpu-bridge-map.c` as a static ARM64 executable (SHA-256
`c24320e56d40f4e1e7618344963a6b51df9a46aeb8aa1a7a2864d6995f23864c`).
On the same responsive control boot after the GFX-off PMGR observation,
an invalid argument was refused. The valid invocation opened `/dev/mem`,
mapped the two exact `0x81000` bridge windows with the diagnostic's
write-only mapping protection, then unmapped and closed them. It reported
`stage=bridge-windows-mapped-no-access` and the iPad remained responsive.
The program contains no loads or stores through the mappings. Host-side
tests use invalid fake pointers to detect unintended dereferences and
exercise failure cleanup.

This demonstrates that this kernel accepts both mapping requests; it is
not a bridge read or write and does not establish that the hardware
responds or that any transaction is safe. The control kernel and GPU-off
state differ from the test boot required for actual bridge replay.


### Fresh diagnostic boot and supervisor preflight

After the user entered DFU and started the PongoOS handoff, the verified
test payload (`m1n1-linux.bin` SHA-256
`06fba59c175dee48e6532257bf3e4c954650b1d3149d7aefbd856809a5ec08c1`)
was booted. Linux reported the expected test-kernel notes
`82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`,
RAM root, and no `/dev/` filesystem mounts. The diagnostic binaries,
module, wrapper and private bridge plan were staged in RAM and their
SHA-256s matched their recorded values.

The GFX PMGR word read `0x00000300` before and after loading the
previously tested inert consumer module. Its build-ID note matched
`b471f3c159c4d326ec466f78967dd5a57ecf1e6d3af9665b93f1ff4ba5f617fb`;
runtime status was `suspended` and usage 0. No power transition was
requested. The progress-gated watchdog supervisor then ran its
synthetic-success control mode, reported disarm, and the same boot
remained responsive more than 23 seconds later with the consumer still
suspended and usage 0. Captures are private under
`artifacts/live/private/gpu-observations/` with names
`2026-11-05-testboot-pmgr-baseline-02.log`,
`2026-11-05-testboot-pmgr-attached-02.log`, and
`2026-11-05-testboot-supervisor-ok-02.log`.

No GPC, bridge or GPU-core register was accessed. This establishes the
staging and control checks only; it does not establish safe bridge writes
or watchdog recovery from a blocked GPU transaction.


### Second checkpointed GFX power-domain transition

On the fresh verified test boot, the staged consumer remained suspended
with runtime usage 0 and the host-persisted PMGR observation was
`0x00000300`. The module, wrapper, kernel notes and module build ID
matched the reviewed hashes; root was RAM-backed with no mounted `/dev/`
filesystem. The existing collector persisted and acknowledged the
pre-read and pre-power markers. The one-shot PMGR power request returned
`rc=0`. A separate host-persisted PMGR read returned `0x000003ff`
(target 15, actual 15, auto 0, reset 0), and Linux reported the
consumer `active` with runtime usage 1. The shell remained responsive.

The private captures are
`artifacts/live/private/gpu-observations/2026-11-05-testboot-power-02.log`
and `2026-11-05-testboot-pmgr-on-02.log`. This is an additional
power-domain observation only: no GPC, bridge or GPU-core register was
accessed and no firmware was executed. The one-shot consumer deliberately
retains its reference until reboot; no automatic power-down was attempted.
It does not establish GPU die temperature, GPU identification, bridge
safety, or recovery from a bus hang.


### Fresh-boot GPC state-only observation

After the second GFX power-domain transition, the previously built
GPC observer and wrapper matched their expected hashes and its one-shot
guard was absent. The host independently persisted and acknowledged the
PMGR and single GPC state-read markers; PMGR read `0x000003ff` and GPC
`0x201e01000` returned `0x00000000`. The consumer remained active with
runtime usage 1 and the shell remained responsive. The private capture is
`artifacts/live/private/gpu-observations/2026-11-05-gpc-state-02.log`.

This matches the bridge prototype's initial GPC-state gate on this boot.
No GPC-control, bridge or GPU-core register was accessed, and the GPC
state read itself was not protected by the watchdog supervisor. The
result is not evidence of bridge write safety, GPU identification or
future recovery. The GFX power reference remains held until reboot.


### Full supervised bridge-protocol simulation on the iPad

The test boot's GFX domain was already on and the prepared GPC state-only
read had returned zero. A revised supervisor, a simulated bridge binary
and its wrapper were staged in RAM and verified by SHA-256. The simulator
uses the exact private bridge plan and production checkpoint logic but
redirects GPC and bridge accesses to a private RAM array. Its separate
one-shot guard prevents confusion with the real bridge diagnostic.

The host validated and persisted the PMGR observation, the simulated
GPC result, all 66 simulated bridge before/after pairs and the watchdog
disarm marker, issuing numbered watchdog-feed acknowledgements only
after each successful result. The iPad remained on the same boot beyond
the 20-second watchdog timeout. The real bridge-write guard remained
absent, and a separately checkpointed PMGR read still reported
`0x000003ff` with the consumer active and runtime usage 1. The private
log is `artifacts/live/private/gpu-observations/2026-11-05-supervised-bridge-sim-01.log`.

The revised supervisor SHA-256 is
`b70387cf689ba13d63ff95f5c585e14feea50d4cc8ffcc9d5138035aca6d92fa`;
the simulated bridge executable SHA-256 is
`8ea9fbf71ecf19cf5f42c1b2548d35187ae8a89f82fb69d9626404402471359a`.
The offline suite passed 71 checks with 7 skipped. This is an end-to-end
protocol and watchdog test, not a bridge or GPU hardware transaction.
After-store markers on an actual run would not constitute readback.


### Simulation executable identity gate

A review found that the simulated wrapper previously accepted any
caller-supplied executable digest, so a real-MMIO executable copied under
the simulated name could have passed that gate. The wrapper now requires
the exact RAM-backed simulator SHA-256
`8ea9fbf71ecf19cf5f42c1b2548d35187ae8a89f82fb69d9626404402471359a`
before invoking the PMGR observer or any child. The host collector also
verifies the selected simulation or real wrapper hash before starting
the supervisor. The updated simulated wrapper SHA-256 is
`3eae753d93113b09c1988e97fa6fae9ba1a1c67d007876e597b9d5324e07662c`.
Host tests confirm both the simulation's expected executable and the
rejection path. On the running iPad the updated wrapper rejected the real
bridge executable's digest before the PMGR observer, the real one-shot
guard remained absent, and the shell remained responsive. No bridge MMIO
was performed.
