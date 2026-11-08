# J81 GPU: iOS 8.1 offline trace (2026-11-04)

Static analysis only; no hardware access. The iPad5,3 12B410 kernelcache
SHA-256 is `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`.
The reconstructed kernelcache, AGX-only Ghidra project, and decompilations
are private, ignored artifacts under `artifacts/live/private/gpu-offline/`.
The raw Ghidra import covers `com.apple.AGX` at `0xffffff8003281000` to
`0xffffff80032c1000`; external calls and vtable types are not resolved by
that import. Findings below distinguish the evidence from what remains open.

## Firmware

- The prelink personality matches `gpu,t7001` and `sgx,t7001` to
  `AGXAcceleratorG4G_A0`. The kernelcache contains `com.apple.AGX` and
  `com.apple.AGXFirmwareKextG4G`. A function at `0xffffff800328fa28`
  returns the latter firmware-kext name.
- The G4G firmware kext contains build paths naming `METAFW` images for
  `g4g_a0_t0.elf` and `g4g_a0_t1.elf` (strings at `0xffffff8002e3a9a4`
  and `0xffffff8002e3e758`, respectively). AGX contains the classes and
  messages `AGXMetaFirmware`, `AGXAcceleratorG4G_A0::waitForMetaIdle`,
  `RGX_CR_META_BOOT`, and a META-alive timeout. Its firmware boot wait
  routine at `0xffffff800329e894` waits for an alive flag and reports GPU
  firmware boot success or a META timeout.
- Together this is strong target-specific evidence that G4G uses META
  firmware, not merely an inference from the missing ADT node. It does not
  by itself decode the firmware format or prove the complete loading and
  start sequence. No firmware bytes are reproduced here.

## Power and clocks

- At `0xffffff80032a0d44`, a power transition routine calls vtable slots
  `+0x560` then `+0x568` on an object held by the accelerator's provider,
  with the requested state and index zero. These call shapes match the
  previously identified `AppleARMIODevice::enableDeviceClock` and
  `enableDevicePower` slots (see `research/t7000-pcie-hardware-findings.md`,
  “Helper and recovery path resolved”). The object's exact type has not
  been proven in this GPU trace, so that identification remains conditional.
  The routine then invokes another conditional hardware-specific callback;
  this is not a complete GPU power-up trace.
- The captured J81 `sgx` node lists both `clock-gates` and `power-gates` as
  `0x7c`. In the PMGR `devices` table, GFX has ID `0x7c`, `psreg` index 3,
  and `psidx` 4. The `ps-regs` entry 3 selects register block 0 at offset
  `0x20300`. The m1n1 PMGR decoder adds `psidx * 8`, yielding **PMGR
  `+0x20320`**, matching Hoolock's `ps_gfx`. The ID is not itself the
  register index; `0x20000 + 0x7c * 8` does not apply here. This resolves
  the offset from the captured description, not from a hardware read.
- The AGX initialization routine at `0xffffff80032871f0` reads the
  `meta-sw-interrupt` provider property and distinguishes the five-interrupt
  configuration. This supports use of the target's META interrupt resources;
  it does not establish interrupt direction or a safe boot sequence.

## Remaining gate before a hardware test

The initial trace did not establish the `reg[1]` mapping, performance-state
write, provider identity, or first RGX access. The follow-up below resolves
much of the probe sequence. The clock/power calls above must not
be treated as a complete register-level recipe. No boot or MMIO access was
performed. Powering a domain or setting a performance state is a write even
if the intended GPU identity operations are reads. Do not attempt the proposed
ID read until its prerequisites and recovery behavior are understood and the
user separately authorizes the hardware test.

## Follow-up: the G4G probe and GPC mapping

The G4G class constructor sets its vtable pointer to `0xffffff80032aefa0`;
its probe slot at `+0x2a0` points to `0xffffff80032935a0`. The following
is a static reconstruction of that probe, not a tested Linux recipe:

1. The probe examines the provider's `reg` property length. With two
   16-byte entries, it selects resource index 0 for the RGX registers and
   index 1 for GPC. This matches the two regions in the captured J81 ADT:
   `0x201000000` and `0x201e00000` respectively. It maps the RGX resource
   before the calls below; mapping is not itself a register access.
2. After a parent-class probe and a virtual callback whose side effects
   have not yet been traced, it calls provider slots `+0x560` with
   `(1, 0)`, then `+0x568` with `(1, &out, 0)`. The G4G personality names
   `AppleARMIODevice` as provider, and the previously resolved slots in this
   exact kernelcache are `enableDeviceClock` and `enableDevicePower`.
   This is much stronger evidence for the gate calls than the earlier
   transition routine alone, though the first callback remains untraced.
3. If resource 1 maps successfully, it writes 32-bit values in this order:
   GPC `+0x10000 = 0xffff0000`, `+0x0 = 0x40000000`, and
   `+0x1000 = 0x11`. When the GPC-present flag is set it polls bit 4 of
   `+0x1000` until clear, without a visible timeout in this path. The
   target `sgx` node has no `no-gpc` property, but the flag's initialization
   path must be confirmed for this exact probe.
4. The probe then invokes vtable slot `+0x800`. For G4G that resolves to
   `0xffffff80032933cc`, which calls slot `+0x810`; G4G resolves that slot
   to `0xffffff800328de68`. That function reads 32-bit RGX `+0x20` and
   `+0x18`, in that order, and combines fields for the driver's GPU match.
   The observed order is more specific than the original proposed ID read.
5. After the match callback, if GPC was mapped, the probe writes
   `GPC+0x1000 = 0x10` and, when the same flag is set, again waits for bit 4
   to clear. If the power hook's output says it should unwind, it calls the
   power-off hook then the clock-off hook. The exact meaning of that output
   and error recovery need tracing before imitating this cleanup.

Separately, `AppleGPCController` at `0xffffff80032a1bc8` waits for bit 4
of GPC `+0x1000` to clear, then writes `state | 0x10`. This confirms the
register and the earlier A10 analogy, but not that all of the probe's other
writes are unnecessary. The standalone GPC state-change path has a timeout;
the probe's two polling loops do not visibly have one.

The remaining offline task is to trace the performance controller's exact
gate/error behavior and design a bounded test and recovery procedure.
These writes and waits can hang or affect the GPU, so the proposed
hardware operation is not fully read-only and still needs explicit go-ahead.

### Pre-power callback resolved

G4G vtable slot `+0x790` resolves to `0xffffff80032861c4`. It initializes
its GPC-present flag to true, and clears it only if a nonzero `no-gpc`
property is supplied; it similarly reads `model-slow`. It performs no MMIO
access itself. The captured J81 `sgx` node has no `no-gpc`, so this path
selects both GPC bit-4 polling loops. The parent probe called before this
callback is still unresolved; this finding does not establish the first
register access in the entire driver lifecycle.

The exact 12B410 provider implementations at `0xffffff80026656d8` and
`0xffffff8002665788` check the index against their respective gate-array
counts and forward the selected ID to the performance controller; an
out-of-range index returns `0xe00002c7`. In the G4G probe, the return codes
from the two enabling calls are not checked before the GPC accesses. A
future diagnostic should explicitly handle failures and use bounded waits;
the original implementation's unbounded loops are not a suitable recovery
strategy.

### Parent probe resolved

The parent probe pointer at `0xffffff80032ad1c0` resolves to the kernel
symbol `IOService::probe` at `0xffffff80023aee84`. Its entire body is a
single return instruction, preserving the incoming `this` pointer as the
return value. It does not access MMIO or power hardware. Together with the
property-only `+0x790` callback, this closes the two previously identified
pre-power call sites inside this probe. It does not prove what the bootloader
or earlier system initialization has done before the probe runs.

## Follow-up: controller dispatch and cleanup uncertainty

**Correction:** The later “Provider-to-PMGR dispatch” section traces an
intervening `AppleT7001IO` and platform-function path. The base controller
slots discussed below are not the directly established GPU gate path; the
conditional cleanup deduction based on them is superseded.

The `AppleARMIODevice` methods do not directly toggle the PMGR register.
In this kernelcache the clock wrapper at `0xffffff80026656d8` selects the
requested `clock-gates` array entry and dispatches to its controller at
vtable slot `+0x558`; the power wrapper at `0xffffff8002665788` selects
`power-gates` and dispatches to controller slot `+0x560`, passing through
its output pointer. Both return `0xe00002c7` if the requested array index
is absent.

The `AppleARMPerformanceController` constructor identifies its instance
vtable at `0xffffff8002695870`. Its clock slot `+0x558` points to
`0xffffff800266c17c`, which checks and tracks device state, then dispatches
further virtual operations; it is not a simple register write. Its power
slot `+0x560` points to `0xffffff800266c404`, which returns `0xe00002c7`
without writing the output pointer. The `AppleT7000PerformanceController`
instance vtable at `0xffffff80031f2090` inherits both of those entries. Its
clock-path virtual operations include `0xffffff80031ea1c8`, whose code
updates per-device reference counts and recursively handles dependencies,
and `0xffffff80031ea424`, which applies queued changes. This reinforces that
unconditionally switching a raw gate off after a diagnostic could interfere
with other users or preexisting state.

This does **not** yet prove the actual controller object used for J81's
`sgx` provider: the captured PMGR compatible string is `pmgr1,t7001`, while
the 12B410 T7000 controller personality names `pmgr,t7000`. The provider
association and matching behavior still need to be traced. If that exact
T7000 controller handles the call, its inherited power hook leaves the
probe's zero-initialized output unchanged on unsupported, so the probe's
conditional power/clock unwind is skipped. That is a conditional deduction,
not proof that the target's controller or cleanup behaves that way.

The pinned Linux `pmgr-pwrstate` driver already implements a managed power
domain with a target-state poll and a 100-microsecond timeout; `ps_gfx` is
present but has no GPU consumer. This is a candidate foundation for a later
bounded diagnostic, not evidence that it reproduces all of iOS's clock,
reference-count, GPC, or recovery behavior. No test code or boot was made.

## Follow-up: how to resolve the provider mismatch

`AppleT7001IO::start` at `0xffffff8003181414` obtains the `arm-io`
provider's `function-clock_gate` and `function-power_gate` properties and
installs callbacks for them. In the captured J81 ADT both properties point
to phandle `0x1a`, which belongs to the `pmgr` node; their four-character
function selectors differ. This gives a concrete additional route through
the target's `arm-io` platform functions to trace. It does not establish
that the `sgx` provider's `AppleARMIODevice` gate calls take that route, nor
which controller instance ultimately handles them.

The apparent compatible-name mismatch also compares two inputs whose exact
firmware-version relationship has not been established: the 12B410 kernel
and a separately captured J81 ADT. The matching 12B410 IPSW includes
`DeviceTree.j81ap.im4p`, but its payload is encrypted. The next conclusive
static check is to obtain its public decryption key, decode that exact
version's device tree, and compare the PMGR node and `arm-io` gate functions
with the kext personalities. In parallel, trace the assignment of the GPU
`AppleARMIODevice`'s controller pointer and the callback dispatch to the
PMGR handler. A live iOS IORegistry class/provider tree, if one already
exists, could independently confirm actual runtime matching; it is not
required and no new hardware run has been requested or performed.

## Follow-up: matching iOS 8.1 tree and iPadOS 15.8.8 drivers

The matching 12B410 J81 device tree was decrypted locally using the public
key already saved under the ignored `firmware/j81-12B410/keys/`. Its PMGR
compatible is **`pmgr,t7000`**, exactly matching the 12B410
`AppleT7000PerformanceController` personality. Its GPU compatible is
`gpu,t7001`, and its clock and power gate arrays both select ID `0x7c`.
Its `arm-io` gate functions both reference the PMGR node. Thus the earlier
compatible mismatch arose from comparing the 8.1 kernel with a different
captured ADT; it is not evidence of a mismatch within the 8.1 release.
The exact `sgx` controller-pointer assignment is still untraced, so this
establishes a matching candidate, not the runtime object's identity.

The local iOS 15 Mach-O at
`artifacts/live/private/gpu-offline/ios15-kernel` has SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389` and is
byte-identical to the decoded J81 kernelcache in the 19H422 extraction. The
matching BuildManifest digest and raw cache verify its exact 19H422 source
association. Its embedded prelink metadata says `DTPlatformVersion=15.8` and
`DTPlatformBuild=19H402`; this is platform/toolchain metadata, not the
top-level product build. See [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md). This establishes source
provenance, not the binary running on a particular device. The
private cache and decoded 8.1 device tree remain under ignored
`artifacts/live/private/gpu-offline/`.

The newer kernelcache separates `com.apple.AGXG4G`,
`com.apple.AGXFirmwareKextG4G`, `com.apple.driver.ApplePMGR`, and
`com.apple.driver.AppleT7001PMGR`. Its `AGXG4G_A0` personality matches
`gpu,t7001` and declares `IOProviderClass=AppleARMIODevice`; its
`AppleT7001PMGR` personality matches `pmgr1,t7001`, the compatible in the
separately captured J81 ADT. These are static personality criteria, not proof
that the live 15.8.8 `sgx` provider is an `AppleT7001IO` instance or that its
indirect gate calls bind to a particular backing object. See
[`2026-11-08-j81-ios15-applearmiodevice-vtable-candidates.md`](2026-11-08-j81-ios15-applearmiodevice-vtable-candidates.md)
for the bounded 15.8.8 vtable result and its runtime-binding limit. This is
consistent with a driver/device-tree naming change across releases, without
assuming the capture's exact OS version.

Target-specific 15.8.8 G4G driver strings connect GPC and Fender terminology,
including `AGXFenderCommon`'s
GPC performance-state operation and `agxk_fender_meta.cpp`. They also name
`pollFenderReg` and contain a timeout diagnostic with register, mask, and
elapsed time. These are useful cross-version leads for bounded polling, not
yet proof of the particular wait limits, the exact 15.8.8 register sequence,
or equivalence to the 8.1 probe. The newer G4G firmware kext also contains
build paths for G4G `METAFW` t0 and t1 images. No firmware bytes or raw
private device-tree data are reproduced here.

Next, trace the 8.1 provider-controller pointer and compare the 15.8.8
Fender polling implementation and timeout policy at instruction level. No
hardware or MMIO access was performed.

## Follow-up: iPadOS 15 Fender wait and 8.1 provider construction

In the local iOS 15 cache (`DTPlatformBuild=19H402`; source association with
19H422 verified; see [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md)), the `AGXG4G` Fender performance-state setter at
`0xfffffff006698d94` reads `Fender+0x1000` until bit 4 clears, calling the
kernel's `IODelay(10)` between reads. Its loop counter and timeout diagnostic
indicate a nominal **30,000 ms** delay budget. On success it writes
`state | 0x10` to `+0x1000`, reads the same register back, and stores the
requested state in software. On timeout it enters a logging/failure path
instead of proceeding to the normal write; the ultimate failure handler is
not yet resolved. The budget is based on requested delays, not a guarantee
of exact elapsed wall time.

Another 15.8.8 Fender routine at `0xfffffff00669c238` writes either `0x20`
or zero to `+0x20000` and, for the enable case, polls bit 5 there and then
bit 4 at `+0x1000`, again using bounded `IODelay(10)` loops and reporting a
30,000 ms timeout. This confirms that newer G4G has additional Fender
coordination; it does not establish that this routine runs in the 8.1 probe
or that either write should be added to a diagnostic. A diagnostic should
choose and explain its own bounded timeout and error handling, not copy
Apple's nominal 30-second busy wait or assume it is safe for every state.

For the 8.1 GPU provider, `AppleARMIODevice` initialization at
`0xffffff8002665ab0` saves its supplied first argument at `this+0x88`, then
loads `clock-gates` and `power-gates`. The provider wrappers subsequently
invoke the saved object's `+0x558` and `+0x560` slots. Its constructor path
at `0xffffff8002665080` forwards a caller-supplied object into that
initializer. This resolves where the controller pointer is stored and shows
it is injected during construction, but the source and runtime class of
that supplied object for `sgx` still need to be traced.

No hardware access occurred. The timeout path, exact controller association,
and recovery after a partial power/GPC transition remain open.

## Follow-up: GPU ID interpretation and pinned Linux support

The pinned Linux `drivers/gpu/drm/imagination/pvr_device.c` supports two
identity layouts. Its legacy path reads 32-bit `CORE_REVISION` at `+0x20`
and `CORE_ID` at `+0x18`: B and V are the revision's bits 23:16 and 15:8;
N and C are the low 16 bits of CORE_ID split into the upper and lower
bytes. This is consistent with the 8.1 G4G identification routine's two
32-bit reads. Raw values should be preserved, not only a decoded string.

The same Linux driver first tries a **64-bit packed BVNC at `+0x20`**:
B, V, N, C occupy successive 16-bit fields from most to least significant.
It falls back to the legacy path if packed B is zero. Therefore the two
32-bit reads proposed in the earlier feasibility note are sufficient for a
legacy decode, but **do not by themselves capture the full packed format**.
This does not establish which layout J81 exposes, nor does it establish that
an additional `+0x24` or 64-bit MMIO access is safe; width and access
prerequisites need separate justification before any hardware plan.

The 12B410 G4G static initializer at `0xffffff800328fb2c` constructs two
match entries labelled `G4G A0` and `G4G A1`: branch/version bytes `7,3`
and `7,5`, with packed table constants `0x07030803` and `0x07050803`.
The matching routine at `0xffffff80032933cc` normally matches branch and
version, and has fallbacks. These entries provide useful candidates, not a
measurement of which revision is fitted to this iPad or a guarantee that
the table's full constants equal its hardware BVNC.

In the project's pinned Linux source, `pvr_gpu_support_level` explicitly
lists only `33.15.11.3`, `36.52.104.182`, and `36.53.104.796` as supported.
Other IDs are classified unknown and rejected by default. The experimental
support switch can bypass that check, but it does not supply missing feature
data, compatible firmware, or an Apple platform implementation. The driver
constructs a firmware filename from the full BVNC and firmware ABI version;
identifying the GPU alone therefore cannot establish that its firmware or
host protocol is compatible.

This is a source and binary comparison only. No extra register read, driver
load, or hardware operation was performed.

## Provider-to-PMGR dispatch: resolved static path

**Correction:** The later “T7000 power callback override” section finds
that the T7000 controller installs its own callback before parent startup.
The default-stub deduction in this section is not the normal T7000 path.

The 12B410 `AppleARMIO` child publisher at `0xffffff8002665130` invokes its
`+0x570` child factory as `(this, this, child)`; the factory at
`0xffffff8002665074` forwards the second argument into the new
`AppleARMIODevice` initializer, which stores it at `this+0x88`. The matching
J81 `arm-io,t7001` personality is `AppleT7001IO`; its instance vtable at
`0xffffff80031820f0` keeps that child factory and overrides gate slots
`+0x558` and `+0x560` with `0xffffff8003181b64` and
`0xffffff8003181bf0`. Thus, when the normal child-publishing path handles
`sgx`, its provider calls go first to **AppleT7001IO**, not directly to
the performance controller. This corrects the abbreviated dispatch
interpretation above.

The T7001IO overrides obtain the `function-clock_gate` and
`function-power_gate` platform-function objects identified during its
start and invoke their slot `+0x78`. The 8.1 J81 `arm-io` device tree
points both function properties at the matching `pmgr,t7000` node. The
8.1 `AppleARMPerformanceControllerFunctionClockGate` and `...PowerGate`
classes implement slot `+0x78` as tail calls to the resolved performance
controller's `+0x680` and `+0x688` slots respectively. For the T7000
controller those slots are `0xffffff800266aaa8` and
`0xffffff800266aae4`: they dispatch through a common workloop gate using
cached clock and power callback pointers.

The performance controller's startup routine at `0xffffff8002667a6c`
initializes those callback pointers from its own vtable slots `+0x558` and
`+0x560` when no prior callbacks are installed. The T7000 instance vtable
has `0xffffff800266c17c` and `0xffffff800266c404` in those slots: the
latter returns `0xe00002c7` without writing the output. Therefore, **if**
the normal matching and default-callback initialization take this path, the
probe's power call returns unsupported, leaves its zero-initialized output
at zero, and its conditional clock/power unwind is skipped. The clock call
still goes through the reference-counted controller path. This conclusion
is stronger than the earlier direct-vtable deduction, but remains a static
result: callback replacement, platform-function resolution, and actual
runtime state have not been observed on the device.

Practical consequence: do not assume that a failed power-hook return in the
Apple probe means the preceding clock request had no effect, or that a raw
power-off write reproduces Apple cleanup. Trace any callback replacement and
actual gate behavior before choosing a Linux diagnostic's ownership and
failure policy. No hardware was accessed.

## T7000 power callback override: correction and cleanup flag

The T7000 startup at `0xffffff80031e6fc8` stores
`0xffffff80031e7bbc` into the power callback field `this+0x2a8` **before**
calling its parent startup. The parent only substitutes the vtable default
if that field is null. Consequently the default `0xe00002c7` stub identified
above is not the normal initialized T7000 callback, and the earlier
unsupported-return / always-skipped-unwind deduction must not be used.

The installed callback at `0xffffff80031e7bbc` initializes a non-null output
to zero, tests a software bitmap indexed by the device ID, sets the output
to one if its bit was set, clears that bit, and returns success. The callback
itself contains no MMIO access and does not use its enable argument. The
bitmap can be set by the PMGR state-transition routine at
`0xffffff80031eb4b4`: after a transition, when the state register's bit 8
is set, it records the corresponding nonzero device ID. The Linux PMGR
header names bit 8 `WAS_PWRGATED`. This supports interpreting the output as
a **consumable recorded power-gating indication**, not a direct read of the
current power state or a generic ownership count. Further analysis is
needed to establish all bitmap initialization, writers and call ordering.

In the G4G probe, a nonzero callback output triggers the later power-off
then clock-off calls; a zero leaves that conditional unwind unexecuted. The
actual result depends on the bit recorded for GFX at runtime. No Linux
cleanup procedure should assume either result from the static trace alone.
No hardware access occurred.

## Follow-up: matching 8.1 GFX clock record and cleanup flag

The 12B410 J81 PMGR tree uses a 44-byte `device-clocks` record format,
not the `devices`/`ps-regs` format in the later captured tree. The table
loader at `0xffffff80031e9af4` reads byte 3 as the device ID, bytes 8–11
as up to four dependent device IDs, and bytes 12–15 as up to four PMGR
power-state indices. The `GFX` record has ID `0x7c`, no nonzero dependent
IDs, and power-state index **100** (`0x64`). No other record in this 8.1
table lists that index. The controller maps index 100 to GFX ID `0x7c`;
its state-register calculation `0x20000 + 100 * 8` independently yields
`+0x20320`. This confirms the address in the actual 8.1 source tree, not
just in the later captured description.

The T7000 PMGR startup zeroes both the index-to-ID table and the bitmap,
then populates the index-to-ID table from the `device-clocks` records. Its
state transition routine at `0xffffff80031eb4b4` records GFX's bit when a
transition involving state index 100 observes the `WAS_PWRGATED` bit and
index 100 maps to device ID `0x7c`. The power callback consumes and clears
that GFX bit. That is the source of the probe's conditional cleanup flag;
it is not a direct read of the PMGR register at callback time.

The clock implementation can alter reference counts and queues, while the
PMGR state-transition code polls for target/actual state equality with no
visible timeout. The record's lack of dependent device IDs does not prove
that all surrounding clocks, voltage, firmware, or platform setup are
unnecessary. The bit's actual value remains unknown without runtime
observation, and the matching driver path's other bitmap writers have not
been exhaustively ruled out. No hardware access occurred.

## Follow-up: firmware image handling versus Linux

**Correction:** The later “META LDR format identified” section shows that
the record structure matches the META LDR format documented in the pinned
Linux source. The earlier description of the structure as Apple-specific is
superseded; the firmware ABI and Linux container requirements remain distinct.

The 12B410 `AGXMetaFirmware` preparation path calls routines at
`0xffffff800329fa14` and `0xffffff800329fbe8`. The former walks a linked
sequence of image records using offsets relative to the input image and
computes aligned allocation regions. The latter walks corresponding records,
copies certain data payloads into a mapped buffer and verifies the copy,
zero-fills other regions, and collects entries from another record type.
Some record types cause failure. This establishes Apple-specific structured
loading behavior, but the input format, full bounds and host/firmware ABI
remain to be decoded; it does not prove the records are a standard format.
A scan of the full 12B410 G4G firmware-kext range found no ELF magic even
though its build-path strings end in `.elf`. Those names describe build
inputs and do not prove an ELF file is embedded unchanged.

The project's pinned Linux `pvr_fw_validate()` instead requires a particular
firmware info header in the final 4 KiB, a valid layout table, the driver's
open-source firmware flag, supported version fields, and an exact BVNC
match. Its META path is therefore evidence about related hardware mechanics,
not a drop-in loader for an Apple image. Do not remove those validation
checks or assume that adding a filename or overriding the GPU-ID check
makes Apple's firmware compatible. No image was executed or submitted to
the GPU.

## Follow-up: 12B410 firmware package structure

The G4G firmware-kext method at `0xffffff8002e391e4` returns a pointer to
its `__TEXT.__const` at `0xffffff8002e39327` and a length of `0x16cd8`.
This identifies the **specific image span**, rather than assuming that the
`.elf` build-path strings denote separate embedded ELF files. The
`AGXMetaFirmware` loader described above expects the image's first-record
offset at byte 8, follows relative record links, and ends when a link equals
`0xffffffff`.

A private, read-only bounds check of that span found 80 distinct linked
records: 58 of type 0, 14 of type 4, two of type 5, one of type 3, and five
whose low five type bits are 16. Every link stayed inside the returned span;
the type-0 source ranges also stayed inside it. Under the 8.1 loader's
interpretation, type-0 records specify a total of 85,980 copied bytes and
type-4 records specify 14,028 zero-filled bytes. These counts are static
structural observations, not a full validation of destinations, execution,
firmware integrity, or runtime compatibility. The original blob remains in
ignored private storage and no bytes are included in this note.

The loader ignores the observed type-16 records through its optional-record
branch; the later META LDR comparison identifies these as comment blocks. Its
parsing does not make the package an ELF merely because path strings mention
`.elf`, nor does it establish compatibility with Linux's separate PowerVR
firmware container. No firmware was executed or sent to the iPad.

## Follow-up: META slave-port register overlap

The 8.1 firmware event handler at `0xffffff800329f6cc` has an event-6 path
that polls RGX `+0xa18` for mask `0x05000000`, then writes `+0xa10` and
`+0xa08` for two META thread register-bank addresses. The pinned Linux
PowerVR definitions identify those same offsets as META slave-port control
and data registers; its ready and global-idle bits are `0x01000000` and
`0x04000000`. The two META addresses selected by Apple are `0x04800000`
and `0x04801000`, matching Linux's `META_CR_CTRLREG_BASE(0)` and `(1)`.
This is specific cross-version evidence that at least this low-level META
register mechanism is shared, not proof that firmware boot, commands, or
memory layouts are compatible.

Each 8.1 poll requests 10-microsecond delays up to a roughly 100-millisecond
counter threshold. The code logs a timeout and then continues into later
operations, including more register writes. A diagnostic or future port
should not infer that continuing after a wedged META port is safe from this
Apple recovery path. The event meaning and complete call context remain
unresolved; this is not a verified power-up sequence. No MMIO was accessed.

## Follow-up: 15.8.8 firmware package comparison

In the local iOS 15 cache (`DTPlatformBuild=19H402`; source association with
19H422 verified; see [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md)), the J81 `AGXFirmwareKextG4G` method at
`0xfffffff0069820c0` returns its `__TEXT.__const` image at
`0xfffffff0059ab9c8`, length `0x1cbb4`. Interpreting that private image
with the **8.1 record-link and type-0 source-range rules** yields a
self-consistent chain: the first-record offset is again `0x1190`, all 88
links and checked type-0 source ranges remain inside the returned span,
and the low-five-bit type counts are 67 type 0, 13 type 4, two type 5,
one type 3 and five type 16. The respective type-0 and type-4 lengths sum
to 109,996 and 26,280 bytes. This is strong evidence that the two releases
retain a related container structure, not proof that all record meanings,
destinations, host protocols or firmware binaries are interchangeable.
The 15.8.8 loader has not yet been traced at the record level. No firmware
bytes are recorded here and neither image was executed.

### 15.8.8 record-walker cross-check

The local G4G driver's instructions at `0xfffffff00668fc40` confirm that
its loader reads the first record offset from image `+8`, follows the next
offset at record `+4` until `0xffffffff`, masks the record type with
`0x1f`, and handles types 0 and 4 while calculating image regions. For
type 0 it reads the referenced 16-bit length and subtracts six; for type 4
it reads the size directly from record `+0xc`. A later walk at
`0xfffffff00668ffbc` again follows the linked records and branches by the
masked type. This confirms the basic cross-release container interpretation
at instruction level, beyond the earlier structural fit. It still does not
establish that all record types, address mapping, firmware ABI, or failure
handling match between releases.

## META LDR format identified

The pinned Linux `drivers/gpu/drm/imagination/pvr_rogue_meta.h` explicitly
describes the **META LDR format**. Its header places `sl_data` at byte 8;
its level-one records contain a 16-bit command and length, a relative next
link at byte 4, and command data beginning at byte 8. Its level-two blocks
have a 16-bit tag and length, with the payload at byte 4. Those fields match
the 8.1 Apple loader and the two privately checked firmware images. The
Linux definitions identify type 0 as `LoadMem`, 3 as `StartThreads`, 4 as
`ZeroMem`, 5 as `Config`, and bit `0x10` as a comment marker. Linux's
`process_ldr_command_stream()` contains corresponding command handling.
This corrects the earlier suggestion that the record structure itself was
Apple-specific and identifies a meaningful reuse candidate.

A bounds-checked offline metadata comparison found that each image has two
configuration blocks containing 27 commands total, all type 2 (`Write`) in
the Linux definitions. Their configuration payloads are byte-identical
between the two releases. Each image also has one 32-byte `StartThreads`
payload; those payloads differ. This is structural evidence only: thread
addresses, memory mapping and the meaning or safe execution of configuration
writes have not been validated. Neither the commands nor their payload bytes
were executed or published.

The shared LDR command format does **not** establish that the stock Linux
PowerVR driver can load or run Apple's firmware. The pinned driver also
requires its own firmware info header, version/feature metadata and ABI,
and constructs shared host/firmware state; those requirements and Apple's
protocol still need separate comparison. The kernel checks must not be
bypassed just because the inner stream is recognizable.

### META LDR configuration targets

The 27 identical `Config/Write` entries in the two private G4G images target
27 distinct addresses in the META address space. Cross-checking addresses
against the pinned Linux META definitions identifies targets including
`META_CR_TXPRIVEXT` (`0x048000e8`), `META_CR_MMCU_LOCAL_EBCTRL`
(`0x04830600`), data- and instruction-cache control (`0x04830018` and
`0x04830020`), and the defined data/instruction cache partition ranges
(`0x04830200`–`0x04830238`). Linux's META boot code also constructs a boot
configuration entry for `0x040000c0`. These correspondences strengthen the
case that the LDR stream describes real META initialization shared across
this hardware family; they do not prove that all addresses, values, ordering,
cache setup, or the firmware ABI are safe or interchangeable on Linux.
They are META-space targets, not established ARM physical MMIO addresses.
No config value or firmware byte is reproduced, and none was executed.

### Thread-record and destination comparison

The 8.1 Apple loader's type-3 path iterates 16-byte records and copies the
second and third words of the record whose first word is `1` into its
firmware object. The pinned Linux `process_ldr_command_stream()` explicitly
ignores `StartThreads` records, so accepting the same LDR container does not
reproduce that part of Apple's setup.

For both private images, the two record IDs are `1` and `0`. In both records,
the second word falls within a raw `ZeroMem` destination and the third word
falls within a raw `LoadMem` destination. That arrangement is consistent with
stack and entry-point fields, but their exact meanings and later consumers
are not yet established. The 8.1 image has 72 nonempty raw destination ranges
and 15.8.8 has 80; neither has overlapping ranges when compared as raw
32-bit addresses. This does not check META global/local aliasing, core-memory
aliasing, mapping to allocations, alignment, or runtime safety. The updated
offline inspector reproduces these aggregates without exporting firmware
bytes. Neither firmware image was loaded or executed.

### Where iPadOS 15 carries the secondary-thread fields

The 15.8.8 type-3 handler at `0xfffffff006690050` selects the record whose
first word is `1`, reverses the order of its next two 32-bit words, and
stores that pair at offset `0xb48` of the driver object. A separate routine
at `0xfffffff00668f770` copies the pair into offsets `0x2f0` and `0x2f4` of
the structure pointed to by the object's `0x220` field. In that same routine,
it stores `0xe1c0000000` at offset `0x300` of that structure. The pinned
Linux META header names the identical value `ROGUE_FW_BOOTLDR_DEVV_ADDR`.

This narrows the thread-record consumer and provides a specific common
bootloader-address constant to investigate when comparing the two host
protocols. The structure's allocation, ownership and firmware visibility are
not yet proven, and matching one constant does not establish matching layouts
or that either thread word can safely be used as a program counter or stack
pointer. The result is static analysis only; no firmware or GPU code ran.

### Cross-release placement of the secondary-thread pair

The 8.1 loader at `0xffffff800329fbe8` saves the second and third words of
the thread-1 LDR record into driver-object offsets `0x5e4` and `0x5e0`,
respectively. The initialization routine at `0xffffff800329d7d8` later
copies those fields into offsets `0x204` and `0x200` of the structure at
object offset `0xc0`. It writes `0xe1c0000000` to offset `0x210` of that
same structure.

The 15.8.8 routine described above puts the corresponding record words at
`0x2f4` and `0x2f0`, with the same constant at `0x300`. All three offsets
therefore moved by `0xf0`, while the word order and the constant's position
relative to the pair stayed the same. This is concrete evidence of a
conserved local arrangement across releases, not proof of identical full
structure layouts, allocation/ownership, firmware visibility, or meanings of
the individual words. The decompiled functions remain in ignored private
artifacts; no firmware or GPU code was executed.

### iOS 8.1 initialization-structure allocation

The 8.1 setup routine `0xffffff80032998d8` obtains an allocation object,
calls its `+0x90` virtual method with a provider-held argument, and retains
the returned object. It then obtains one base through the allocation object's
`+0x80` member and another through the returned object's `+0x80` virtual
method. Both bases are advanced by the same aligned offset and saved in
driver-object slots `0xc0` and `0x118`, respectively. The first is the
structure receiving the thread-1 pair at `+0x200` and `+0x204`.

Later, `0xffffff800329d7d8` passes the second, correspondingly offset value
through driver virtual method `+0x140` with argument `1`, then stores the
32-bit result at `+0x5c` in another object-held structure. The recovered
`0xffffff80032998d8` setup routine also contains several independent calls to
the allocator, each followed by its own `+0x90` mapping call and `+0x140`
address-view call. Thus the safe conclusion is **multiple allocation classes,
each potentially exposing more than one address view**; it is not evidence
that the two observed bases belong to one allocation. The allocation/mapping
types and each encoded address's final consumer remain unresolved. The vtable
calls and common offsets are observed facts; calling any returned value a GPU
address or assuming firmware access would be an inference requiring further
evidence. No hardware or firmware was touched.

### Core-memory zero handling differs

The 8.1 Apple type-4 loader skips an entire `ZeroMem` record when its start
falls in the `0x80000000`–`0x8000bfff` window. The pinned Linux META loader
instead skips zeroing for its separate core-memory **data** window beginning
at `0x82000000`; for a `0x8000xxxx` start it clears the global-range bit and
asks its MMU-segment lookup to map the resulting address. The outcome of that
lookup depends on Linux firmware layout and is not established here.

Each private Apple image contains three nonempty zero ranges beginning in the
8.1 window; one range in each starts below `0x8000c000` and extends beyond
it. Thus a loader that classifies the whole record by its first address can
handle that crossing differently from one that splits it at the boundary.
Apple 8.1's skip behavior is directly visible in the decompilation. The
15.8.8 dispatch table sends type 4 to `0xfffffff006690094`; its unsigned
32-bit add, shift and compare at `0xfffffff006690098`–`0xfffffff0066900a4`
skip a whole zero record when its starting address is in
`0x80000080`–`0x8000bfff`. This differs from the 8.1 lower boundary by
`0x80`, but all three relevant zero records in each image fall within both
windows. In particular, the boundary-crossing record is skipped by each
release's own guard. The inspector tests the 15.8.8 guard's boundary values.
In both images, each thread record's second word falls within a `ZeroMem`
range that its corresponding Apple loader skips. Therefore the earlier raw
range match must not be interpreted as evidence that the loader zeroes those
locations; how the core-memory contents are initialized remains unknown.
These findings are another concrete reason not to feed either image to the
stock Linux loader unchanged. No firmware bytes were extracted or executed.


### GFX clock bridge settings: 2026-11-05

The J81 8.1 PMGR `device-clocks` record for GFX (`0x7c`) has
flag byte `0x06`, followed by bridge selectors `9` and `10`; its
power index is 100. The PMGR initialization routine in the T7000
driver reads `#bridges` and `bridge-reg-index`, maps each bridge, and
loads its corresponding `bridge-settings-%d` property as 32-bit
offset/value pairs. The J81 tree has 13 bridges, register index 2,
and 33 pairs each in settings 9 and 10.

When the clock operation reaches the queued special-action path,
`0xffffff80031ea58c` handles flag bit 1 on enable by calling
`0xffffff80031eb648` for the two selectors. The AArch64 instructions
at `0xffffff80031ea60c`–`0xffffff80031ea624` confirm the second
selector is passed as an argument despite the decompiler omitting it.
The latter function writes each pair to its corresponding mapped bridge.
Flag bit 2 also calls the SoC-busy accounting path. These actions are
conditional on the clock state machine and its queued bitmap: the
record alone does not show which actions ran on the current boot.

The Linux diagnostic's successful GFX PMGR power request establishes
none of these bridge settings. The inspected m1n1 source has no literal
`bridge-settings` or `bridge-reg-index` references; this search does
not exclude earlier boot firmware or another indirect mechanism. Their
current values, ordering requirements, and safe recovery remain unknown.
Consequently the GPC and GPU ID experiment must not assume that the
power-domain observation reproduces Apple's prerequisite clock setup.
Private decompilation and instruction logs are in
`artifacts/live/private/gpu-offline/`. No bridge table was applied.


### Bridge windows and newer device tree: 2026-11-05

For the 8.1 PMGR node, bridge register index 2 plus selectors 9 and
10 selects PMGR `reg` entries 11 and 12. Their child addresses are
`0x01f00000` and `0x01f80000`, each of size `0x81000`. The `arm-io`
range translates child address 0 to physical `0x200000000`, giving
bridge bases `0x201f00000` and `0x201f80000`. This translation and
these table mappings are derived from the offline device tree and
driver code; no register reads or writes verified their behavior.

A separately captured J81 Pongo ADT has the same bridge register
entries and the same 264-byte contents for both `bridge-settings-9`
and `bridge-settings-10`. All four tables (two selectors in each
source) compare byte-for-byte equal; each hashes to
`b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4`.
The captured GFX device record includes selectors 9 and 10 too, though
its 48-byte format differs from the 8.1 44-byte record, so the old
flag interpretation must not be applied directly. The capture is a
previous Pongo ADT, not a live register snapshot and not proof that
any settings were executed on the current boot.

The inspected m1n1 source matches the pinned input's NAR hash. Its
`pmgr_adt_power_enable` resolves power IDs and sets their PMGR target
state, but does not itself load the bridge tables. No literal bridge
property references were found in that source or the local m1n1
patches. Other earlier boot stages or indirect mechanisms remain
possible. The iPadOS 15 kernel has bridge-property string references in
both ApplePMGR and AppleT7000 code; those references establish the
properties are recognized, not that the 8.1 call sequence is identical.
The mapping, flag handling, readback semantics, and safe sequence in
the newer driver still need analysis.


The 15.8.8 AppleT7000 implementation can now be compared more
precisely. Its initializer at `0xfffffff006c92cf4` reads the bridge
count and register-index properties, maps one region per bridge, and
records each `bridge-settings-%d` property as offset/value pairs.
`0xfffffff006c97278` writes each selected pair into the indexed region.
The conditional path at `0xfffffff006c961f8` calls that writer for two
selectors when flag bit 1 is set and the operation is enabled. The
second selector argument is confirmed in instructions at
`0xfffffff006c96294`–`0xfffffff006c962a0`. Like the older code, this
is a 44-byte clock-record path; the separately captured 48-byte GFX
`devices` record cannot be substituted for it. Provider matching and
the origin of the newer clock records remain to be established before
asserting that this path executes for J81 in 15.8.8. The private code
slices and Ghidra logs remain under `artifacts/live/private/gpu-offline/`.


### J81 newer PMGR path: 2026-11-05

The 15.8.8 kext personality for `AppleT7001PMGR` matches the captured
J81 PMGR compatible `pmgr1,t7001`; `AppleT7000PerformanceController`
in the similarly named AppleT7000 kext instead matches `pmgr,t7000`.
The AppleT7001PMGR kext's class registration identifies
`AppleT7001PMGR` as a subclass of `AppleT7000PMGR`, a different class
from the older AppleT7000 performance controller. Its superclass
metaclass reference points into the shared ApplePMGR kext. Personality
matching and inheritance identify the intended path but do not by
themselves prove a runtime provider instance on the current Linux boot.

The captured PMGR `devices` property consists of 48-byte records. Its
GFX record has ID `0x7c`, count 2 at byte `0x18`, and selectors 9 and
10 at bytes `0x1c` and `0x1d`. In shared ApplePMGR,
`0xfffffff006bbf7a4` loads the bridge maps and individual tables,
while `0xfffffff006bd90a8` loops over a device record's bridge count and
selectors. Under its legacy table-format branch,
`0xfffffff006bd3dc8` iterates offset/value pairs and dispatches each
write through virtual operation `+0x998`. The capture has the separate
`bridge-settings-9` and `bridge-settings-10` properties and no explicit
`bridge-settings-version` property. The alternate-format branch and
initial/default version value still warrant verification.

The shared PMGR routine `0xfffffff006bd81a8` calls the bridge loop on
a device transition when its requested state is `0xf`, after a state
operation; it uses a different bridge-related path on the way down.
Another routine invokes the loop for already-active devices. This
connects the captured GFX selectors to a conditional power-up bridge
setup in the newer shared implementation. It does not prove the exact
runtime call chain, write completion, register contents or whether an
earlier boot stage retained them. We have not executed that sequence,
and the 66 raw bridge writes must not be treated as safe merely because
the tables are public in an ADT. The decompilations and code slices are
kept in ignored private artifacts.


### iPadOS 15 bridge write dispatch: 2026-11-05

The iPadOS 15.8.8 AppleT7001PMGR object constructor installs the vtable
at `0xfffffff006fe69c0`. Its bridge-write slot `+0x998` resolves to
`0xfffffff006bd3d38` in the shared ApplePMGR code. That function
performs a direct 32-bit store of the supplied value at the indexed
bridge's mapped base plus the supplied offset. The AppleT7000PMGR
superclass vtable resolves the same slot to the same function. Thus
the legacy pair loop previously identified can issue raw stores, rather
than an understood masked update or a demonstrated readback operation.

Each of the two identical 33-pair GFX tables contains 33 distinct,
word-aligned offsets; 32 offsets are in the `0x40000` subrange. One
table value has its high bit set; treating the registers as ordinary
readable storage would be speculative. The
captured ADT has no explicit `bridge-settings-version` property. The
initializer assigns the version field when that property exists, and
the bridge writer uses version 0 for direct offset/value pairs, but
the absent-property default is not yet proven. These observations do
not establish MMIO read safety, current register values, retained state,
or whether issuing the writes is safe on Linux. No bridge, GPC or GPU
register was accessed in this follow-up.


### Orchard cross-check: 2026-11-05

[Orchard PR 73](https://github.com/OrchardLinux/orchard/pull/73),
head `6aa778c7e4b681ce521654b777d178b4f2e9c577`, reports J96 (A8,
not J81 A8X) experiments through 5 November. Its author reports a
successful GFX PMGR transition and Fender probe/state 1, followed by
a repeatable SoC hang on the first 32-bit RGX read at `0x201000020`.
The report does not establish the bridge settings, complete register
sequence, or cause of the hang. The neighboring hardware result is a
strong reason not to infer RGX accessibility from PMGR on or Fender
state 1; it is not proof J81 will behave identically.

[A9 discussion](https://github.com/OrchardLinux/gpu/pull/2#issuecomment-6612910581)
reports an iOS A9 `isGPURegisterAccessible` predicate checking PMGR,
Fender pstate and a firmware power-down handshake. This is a useful
lead to look for in J81's own G4G driver, not a validated J81 rule.
The A9 authors report some working driver behavior but their GPU PR
is a discussion with an empty commit. [Mesa PR 6](https://github.com/OrchardLinux/mesa/pull/6)
publishes a separate A9 G5P experimental userspace series and reports
hardware results for earlier A9 integration builds; it does not provide
a J81 kernel or firmware backend. [Linux PR 1](https://github.com/OrchardLinux/linux/pull/1)
is a draft shared PowerVR reset-error fix with host-only tests; its
own description says it does not establish acceleration on a device.

At the check, Orchard's GPU default branch remained at `42f6add`
(2026-11-03 UTC), already present in the private checkout. The next
static comparison should trace G4G's corresponding register-access
predicate and its pstate/clock preconditions, and investigate bridge
read semantics and GFX power sequencing without issuing a speculative
RGX access.


### G4G runtime register-access guard: 2026-11-05

In the 15.8.8 G4G driver, the register-dump routine
`0xfffffff006699740` calls the firmware object's virtual slot `+0x240`
before dumping GPU registers; failure leads to the diagnostic string
`GPU Power Off: Registers unavailable`. The G4G accelerator vtable
`0xfffffff006f2f2d0` has firmware-factory slot `+0x848` pointing to
`0xfffffff00669afa8`, which constructs `AGXMetaFirmware` with vtable
`0xfffffff006f2de28`. Its `+0x240` slot points to
`0xfffffff006692828`. This supports resolving the runtime guard for
the G4G class rather than assuming the A9 implementation applies.

With its controller pointer at `+0x160` present, the guard calls
controller slot `+0x18` twice and requires its returned value to be
at least 1 and no greater than a maximum in a separate state object.
It also requires controller slot `+0x78` to return zero. The G4G
accelerator's controller-factory slot `+0x850` creates the object
with vtable `0xfffffff006f2fee8`; its `+0x18` reads the low nibble
of mapped base `+0x1000` when the object is enabled, and `+0x78`
extracts bit 29 of a 32-bit read at mapped base `+0`. The object's
initializer receives its base from the caller; the final provenance
of that mapping remains to be traced. These offsets and operations
match the independently reported A9 Fender guard, but the first
condition is two reads rather than an atomic snapshot, and the guard
alone does not prove a Linux implementation safe against concurrent
power transitions.

This check guards a runtime register dump after firmware/controller
objects exist. It has not been shown to guard the early model-ID
probe, and it cannot be applied blindly to an uninitialized controller.
The non-null-controller branch shown here does not directly check the
Linux PMGR reference; the null-controller branch has separate flag and
software-state logic. Neither the currently powered J81's GPC state nor
bit 29 has been read. No new MMIO access, firmware execution or power
change was performed. Decompilation and vtable evidence remain in the
ignored private artifacts.


The 15.8.8 accelerator start routine `0xfffffff00666d6e4` obtains
the same global mapped object through its `+0x78` method and uses
the returned base for a `+0x1000` state write and bit-4 wait. The
firmware-controller initializer passes that global object's `+0x78`
result into its G4G controller object, whose initializer stores it at
`+0x10`. This independently links the guard's base to the driver's
Fender/GPC state-control mapping; it does not establish current state
or make reading the mapping safe in isolation.


### iPadOS 15 early G4G identification: 2026-11-05

The 15.8.8 G4G accelerator's vtable `0xfffffff006f2f2d0` resolves
slot `+0xa38` to `0xfffffff00668459c`, which calls slot `+0xa48`; for
G4G the latter resolves to `0xfffffff00669bb54`. That last function
reads 32-bit words from the mapped RGX block at `+0x20` then `+0x18`.
It uses selected revision and core-count fields to fill match data.
This establishes the read order in the newer driver's match path as
well as the older one; these reads do not establish an actual J81 ID.

In the new driver's first-provider path, the instructions at
`0xfffffff006683918`–`0xfffffff0066839e4` request the provider's
clock and power operations, conditionally perform GPC setup (including
`+0x10000`, `+0` and `+0x1000` writes), wait for bit 4, and invoke
`IODelay(10)` before calling the match slot. The 8.1 probe at
`0xffffff80032935a0` likewise calls `IODelay(10)` after its GPC poll
and before its match call; both delay symbols were checked against
their respective kernel symbol tables. The 15.8.8 setup and even the
first-provider power sequence are conditional; the already-matched
provider path also differs. Neither observation is a complete Linux
recipe or a proof of the J96 hang's cause.

The `AGXMetaFirmware` runtime guard described above is not visibly
called by this direct match dispatch, and the firmware object is
constructed later in the separate start routine. That supports keeping
the runtime access predicate distinct from early identification; it
does not rule out checks or setup hidden in earlier virtual calls,
boot firmware or the provider. In particular, power on, GPC state 1,
and a 10-microsecond delay are not sufficient evidence for a safe RGX
read, given the J96 report. No GPU, GPC or bridge registers were
accessed in this follow-up.


### Default bridge-format evidence and live PMGR recheck: 2026-11-05

The 15.8.8 `AppleT7001PMGR` allocation path calls
`OSObject_typed_operator_new` at `0xfffffff007689f84`; its normal zone
allocation path passes flags `0x000d1004` to `zalloc_flags`. Apple's
[XNU 8020-series allocator header](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/osfmk/kern/zalloc.h)
defines `Z_ZERO` as bit `0x0004` and documents zero-filled allocation.
The running binary identifies itself as xnu `8020.241.44`, not the
public `8020.140.41` reference. The shared PMGR constructor and J81
subclass constructor were inspected; no direct write to the format
field at object offset `0x2680` was found there. The shared initializer
assigns that field if the `bridge-settings-version` property is present;
this captured tree lacks that property. Together this supports a
zero/legacy-format default on the normal allocation path, but is still
an inference: indirect initializer effects and the capture's exact
OS-version relationship have not been fully ruled out. It is not a
hardware-state observation.

A separately acknowledged PMGR read on the current boot produced
`0x000003ff` (target 15, actual 15, auto 0, reset 0), using the
previously verified reader and host-persisted checkpoint. The shell
remained responsive, and Linux reported the test consumer active. The
private raw capture is
`artifacts/live/private/gpu-observations/2026-11-05-gfx-followup-02.log`.
This reports only the PMGR word; it says nothing about bridge values,
GPU accessibility or die temperature. No other hardware register was
probed or modified in this follow-up.


### Bridge actions and already-active PMGR state: 2026-11-05

The iPadOS 15 shared-PMGR routine `0xfffffff006bc6c20` returns the low
nibble of the device's PMGR state word. In the transition routine
`0xfffffff006bd81a8`, a loop enters its increasing-state branch when
that nibble is less than the requested state. It calls the bridge setup
loop `0xfffffff006bd90a8` for a device when the requested state is `0xf`,
after issuing the state operation. A separate initializer/replay path
`0xfffffff006bcd2c8` can call the same bridge setup for devices it tracks
as active. Thus an implementation that observes GFX target already 15
and simply skips a redundant power request must not assume it reproduced
Apple's bridge operations. Conversely, the replay path means we must
not claim Apple always skips them for already-active hardware. The exact
entry conditions for each path still need verification.

The captured 8.1 J81 tables show selectors 9 and 10 each contain 32
offsets at `0x40000` and above plus one at `0x18`; both tables are
identical and their windows have distinct bases but overlap by `0x1000`. This grouping does not prove
the registers are normal readable storage or identify read side effects.
The iPad remained responsive with Linux reporting GFX on and its consumer
active. No bridge, GPC or GPU-core register was read or written.


### GPC and bridge address separation: 2026-11-05

The matching 8.1 J81 tree declares the GPC resource as child address
`0x01e00000`, length `0x100000`, translated to the physical interval
`[0x201e00000, 0x201f00000)`. The separately captured J81 ADT declares
the same resource address and length. Thus both proposed observer words,
`0x201e00000` and `0x201e01000`, lie within the declared GPC resource.
The GFX bridge-9 mapping begins at the immediately following physical
address `0x201f00000`, with bridge-10 at `0x201f80000`. The distinct
resource windows support the address calculation; they do not establish
that a GPC transaction responds before the bridge configuration or
that any mapped register is safe to read.

In the 8.1 controller's conditional enable flush
`0xffffff80031ea424`, the pending power-state loop runs before the
queued special-action loop when its enable argument is nonzero; the
reverse ordering is used for disable. GFX's special-action record can
select both bridge tables, but the actual pending bitmaps and clock
reference counts on this Linux boot are not observed. The iOS 8.1 and
15 probe traces both show GPC accesses after their clock/power calls;
we have not located a matched J81 boot-stage GPC read before those
calls or found evidence that Linux/m1n1 applied equivalent GFX bridge
settings. This leaves the first observer read unqualified.


The 8.1 PMGR clock hook `0xffffff800266c17c` calls virtual slot
`+0x690`, then passes its returned work mask to slot `+0x698`. The
T7000 instance vtable resolves those to `0xffffff80031ea1c8` and
`0xffffff80031ea424`, respectively. The first routine only queues
special actions when its reference-derived state differs from its
recorded bitmap; GFX's record has special flags `0x06`, selectors 9
and 10, and power index 100. In the enabled flush, queued power-state
work precedes the queued special actions. This makes the conditional
route from the clock request to the bridge settings more concrete,
but the code does not show the bitmap or reference counts that Apple's
boot would have at that moment. It also does not show that bridge setup
is necessary for a read of the separate GPC control window.


### Static bridge plan cross-check: 2026-11-05

Generated a private comparison plan at
`artifacts/live/private/gpu-offline/gfx-bridge-static-plan.json` from
the 8.1 J81 device tree, translating selectors 9 and 10 through the
PMGR resource entries and arm-io range. All 66 entries are word-aligned,
inside their declared mappings, and resolve to distinct physical
addresses. Each selector's 33 offset/value pairs independently matches
the earlier captured J81 ADT byte for byte and in order. This plan is
for static comparison only: it does not include verified hardware state
or justify executing the writes.

On the running test system, a separately built `--map-only` observer
successfully mapped and unmapped the GPC interval without issuing a
register load. A host-side fake mapping that is deliberately invalid
for dereference also passes this mode. Linux's successful map and this
software-path check cannot demonstrate that GPC will answer a load.


### Runtime guard is insufficient for early RGX access on this boot

On the J81 Linux test boot, a checkpointed read reported PMGR
`0x000003ff`, GPC `+0x1000=0x00000001` and GPC `+0=0x40000000`
(bit 29 clear). The immediately following 32-bit RGX `+0x20` read did
not return before the 30-second host deadline. These observations
match the earlier caution: the iPadOS runtime predicate's visible
state/handshake conditions are not sufficient by themselves to make an
early GPU-core read complete in this Linux environment. The unobserved
bridge programming, additional clocks and boot-time initialization
remain candidate differences; the test does not isolate which, and
a host timeout does not by itself prove the precise fault mechanism.
The user reported a restart and re-entry to DFU, and the host observed
the DFU USB identity afterward. The private raw capture is
`artifacts/live/private/gpu-observations/2026-11-05-gpu-id-01.log`.


### Repeatable bridge comparison and counter path: 2026-11-05

The new offline tool `tools/audit_gpu_bridge_plan.py` validates the
matching 8.1 J81 PMGR clock record and GPU gates, translates each
bridge mapping through the `arm-io` ranges, checks the ordered offsets
and mapping bounds, and compares both 33-pair tables with the separate
captured J81 ADT. It prints summary hashes and addresses, not table
values. Synthetic tests reject mismatched data, gates, mapping size,
ambiguous range translation and duplicate captured properties. The
real private inputs pass, with selectors 9 and 10 each hashing to
`b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4`.

The iPadOS 15 shared PMGR initialization reads optional
`bridge-counters` and `bridge-counter-configs`; its GFX bridge loop
performs an extra counter action only when the per-bridge counter
pointer exists. Neither property appears in the captured J81 PMGR
node. The initializer zeroes the per-bridge pointer and assigns it
only when the corresponding optional property exists, so that extra
branch is not expected for this captured tree. This remains a static
conclusion about the capture, not evidence of live settings or a
verified write sequence. The first table entry has its high bit set;
its hardware semantics, safe readback and safe failure recovery remain
unknown. No bridge or GPU register was accessed.


The cross-check also validates the captured GFX record's identity,
bridge selectors and auxiliary selector, and checks its two bridge
region indices against the 8.1 mappings. The auxiliary selector is zero.
These checks strengthen the comparison of the two static inputs; they
do not establish the live hardware state.


### GFX bridge ownership and mapping overlap: 2026-11-05

A scan of every 44-byte iOS 8.1 `device-clocks` record whose bridge
flag is set finds only GFX selecting bridge 9 or 10. Independently, a
scan of all 98 captured 48-byte J81 `devices` records finds only GFX
selecting either bridge; their decoded bridge counts are zero for 86
records, one for 11, and two for GFX. This associates the two tables
with GFX in both static descriptions, but does not prove exclusive
physical ownership or safety in the live system.

The declared bridge 9 and 10 windows each have size `0x81000` and
overlap by `0x1000` (`0x201f80000` through `0x201f80fff`). The actual
66 planned store addresses are distinct; bridge 10's first store at
`0x201f80018` falls within that overlap. These ranges are translated from the device tree, not observed
register behavior. In particular the software association and distinct
addresses do not establish what the first store does or whether any
store affects shared hardware. No MMIO was issued for this analysis.


### Conditional display-cache side effect of the 8.1 GFX path

Further decompilation of the 8.1 T7000 PMGR code resolves part of the
previously ambiguous GFX flag bit 2. The SoC-busy routine at
`0xffffff80031eb7c0` changes a busy counter and, only when additional
conditions hold, invokes a display-idle control function and may change
the display framebuffer memory-cache configuration and queue a clock
state change. Its setup at `0xffffff80031e8e54` checks `fb-caching`,
`mcc-config-fb-caching`, `function-dispidle_ctrl` and
`disp-fb-mcache-id`. The matching 8.1 J81 PMGR tree has `fb-caching=1`,
`mcc-config-fb-caching=4`, and `disp-fb-mcache-id=0x75`; record `0x75`
is named `DISP-FB-MCACHE`. The same table identifies `DISP0` as the only
clock record with special flag bit 3, whose handler changes the runtime
condition tested by the busy routine.

This establishes a conditional interaction with display caching in the
8.1 Apple implementation. It does not prove the display function is
available, the runtime condition is set, or the interaction ran in a
particular boot. A boot argument can override the `fb-caching` value.
The iPadOS 15 path has not been shown to perform the same action. No
display, PMGR, GPC, bridge or GPU register was accessed for this
analysis. The bridge-only prototype does not reproduce this conditional
display coordination, so it cannot be treated as a complete replay of
the older Apple clock sequence. Decompilations are retained under
`artifacts/live/private/gpu-offline/framebuffer-cache-setup.c` and
`framebuffer-cache-helper.c`.


### iPadOS 15 SoC tuner and GFX/display grouping: 2026-11-05

The captured newer J81 ADT places its tuning policy in a separate
`soc-tuner,t7000` node, rather than the `pmgr1,t7001` node. Its
`fb-caching` and `soc-tuning` properties are both enabled, it declares
`function-dispidle_ctrl` and `function-mcc_ctrl`, and its four MCC
configurations have values 1 through 4. Its device set 0 lists IDs
`0x12`, `0x18`, `0x1d`, `0x74`, and `0x7c`; matching these against
the captured PMGR `devices` records gives MEDIA, ISP, DISP1,
DISP-FB-ACTIVE, and GFX respectively. Device set 2 is `0x1c` (DISP0).
These are declared software policy groups, not proof of electrical
sharing or of a live transition.

The 15.8.8 kernelcache personality `AppleT7000SOCTuner` matches
`soc-tuner,t7000` on `ApplePMGRNub`. Its separately extracted code
references the tuner properties, and its state handler
`0xfffffff006cd827c` conditionally invokes a display-idle function and
selects an MCC configuration when its input state changes. The helper
functions at `0xfffffff006cd8d08` and `0xfffffff006cd8bfc` issue
conditional virtual calls through the respective function objects.
This is evidence of an iPadOS 15 policy path as well as the 8.1 path;
it does not establish which calls happen before GFX bridge setup, the
meaning of each input field, or the corresponding Linux state. Ghidra
failed to decompile the entire start routine because of unresolved
external control flow; property references in the initializer were
verified in instructions, not inferred from the incomplete decompile.
The extracted tuner code and analysis remain private under
`artifacts/live/private/gpu-offline/ios15soctuner*`.

On the running Linux control boot, both DRM card0 and fb0 identify the
`simple-framebuffer` driver. This says which Linux driver owns the
framebuffer, not the live MCC configuration or whether the Apple policy
would be necessary for GPU access. No MMIO or power transition was made.
The finding strengthens the case that a bridge-only replay is incomplete
without establishing that reproducing the tuner is required or safe.


### iPadOS 15 tuner state handler: 2026-11-05

The `AppleT7000SOCTuner` object's vtable at `0xfffffff006ffc548`
contains `0xfffffff006cd827c` at slot `+0x548`. A separate callback
wrapper at `0xfffffff006cd8ab8` passes its fourth argument to that
virtual slot. That establishes the callback-to-handler linkage; the
source and exact interpretation of the callback's four input words
remain unproven. The initializer fetches `devices` and `#device-sets`
from the provider, but an unresolved external path prevents a complete
static trace of their notifications.

The handler's mode selection can be stated without assigning names to
the four input words. For words A, B, C and D at offsets 0, 4, 8 and 12:

- If C is zero, it selects mode 0 when D is zero, otherwise mode 1.
- If C is nonzero and A and B are both zero, it selects mode 3.
- Otherwise, with C nonzero, it selects mode 2.

When the selected mode changes, the driver may call the display-idle
function when entering or leaving mode 3, then selects the corresponding
MCC config through `function-mcc_ctrl`; entering mode 3 stops if the
conditional display-idle helper does not succeed. A change in C's
zero/nonzero state also triggers calls over the configured `devices`
list. These observations describe the static branch, not a hardware
measurement or a safe initialization sequence. In particular, the
order and identity of the callback words are not yet tied to the ADT
device-set numbers, and the observed Linux framebuffer driver does not
provide those Apple runtime counters. No live register was touched.


### PMGR-to-tuner bitmaps and a concrete mode: 2026-11-05

The callback input mapping can now be resolved. ApplePMGRNub's setup
`0xfffffff006be221c` loads each numbered `device-set-%d` into the
corresponding indexed array. The tuner calls a stub resolved from the
15.8.8 kernelcache to ApplePMGRNub `0xfffffff006be3b0c`, which registers
callback `0xfffffff006bdc648`. The callback reconstructs one bitmap per
device set, setting bit N when PMGR's software bitmap reports that the
Nth member is active, and sends the array in message 10. The
`AppleT7000SOCTuner` vtable slot `+0x420` points to
`0xfffffff006cd8ab0`, which checks for message 10 and passes the array
to its mode handler. PMGR updates the underlying device bitmap when
its software state changes to or from state `0xf`. This is a software
state observation, not independent PMGR register readback.

For the captured J81 tree, GFX is bit 4 of set 0 and DISP0 is bit 0
of set 2. If both bits are set, the handler selects mode 2 regardless
of set 1 or 3. The `mcc-configs` array maps mode 2 to value 3. If DISP0
is active and all set-0 and set-1 bits are clear, it selects mode 3,
corresponding to value 4, subject to its display-idle condition. This
explains a concrete way GFX activation can affect Apple's selected MCC
policy. It does not establish that display or GFX are active on the
Linux boot, that the software event ran, the live MCC register value,
or the exact ordering of notifications relative to bridge writes. In
particular it does not justify writing MCC or bridge registers.

`tools/audit_gpu_tuner.py` checks the captured J81 topology and models
this decision; its synthetic tests cover all 16 boolean input
combinations and reject topology changes. Actual capture audit passes;
the complete offline suite passed 67 checks with 7 skipped. This
analysis supersedes the preceding uncertainty about the callback word
order. No MMIO or power transition was performed.


### MCC table comparison and display-idle target: 2026-11-05

The matching `mcc,t7000` node in both the iOS 8.1 J81 tree and the
captured newer J81 ADT contains the same 220-byte `config-data` table
(SHA-256 `9fabbaa9661c4475c3f7cb18b403b657de212ddd4f4ee731c1b4aa79a7323823`).
The 15.8.8 controller treats it as five 44-byte records. Records 3 and
4 are identical in all 44 bytes. Records 0, 1 and 2 are also identical
to one another; record 3 differs from record 0 in one 32-bit word, the
second. The controller method at `0xfffffff006c91c3c`, associated with
`_mccEnableCache`, indexes the requested record and uses its first two
words in masked updates to its mapped `+0x794` register. Thus, for the
particular display-active policy change from configuration 4 to 3,
Apple selects identical table content; it is not a change in the data
used by this method. This does not establish the current Linux register
value, that executing the writes is side-effect-free, or equivalence of
all other policy actions.

This five-record interpretation is specific to the 15.8.8 consumer. The
matching 12B410 iOS 8.1 bytes are parsed by that older consumer as eleven
20-byte records; see `research/2026-11-07-j81-mcc-ios81-record-stride.md`.
The shared DT byte string does not imply that the two OS versions use the
same record stride or selector semantics.

The newer tree's `function-dispidle_ctrl` phandle `0x5a` resolves to
`disp0`, compatible `adbe0,t7000`; the 15.8.8 kext personality matches
`AppleMobileADBE0`. The display driver's
`AppleDisplayPipeSetSystemIdleStateFunction::callFunction` at
`0xfffffff006cbc444` calls `0xfffffff006cb8d60` with a boolean input.
That function can update display-idle state and invoke a workloop or
event-source path, conditional on driver state. The function name and
matching phandle support the display-idle interpretation, but the full
function registration and resulting hardware operations have not been
resolved. Identical MCC table rows therefore narrow one suspected
difference; they do not prove the display-idle transition is harmless
or remove the separate bridge-write uncertainty.

The tuner audit now checks the MCC table length, compares rows 3 and 4,
and optionally verifies the older 8.1 tree against the captured newer
table. Its tests include a synthetic unequal-row case. The offline suite
passed 67 checks with 7 skipped. No hardware register was accessed.


### Display-idle callback follow-up: 2026-11-05

The matched display-idle function calls `0xfffffff006cb8d60`. Its
visible code first invokes idle-state evaluation, checks a display
object state, then conditionally stores the requested boolean in a
display-side object and invokes event-source methods. The follow-up
idle evaluation compares stored and calculated state and conditionally
dispatches through an indirect jump. These operations support a
software display-idle notification with conditional further work;
they do not identify the ultimate hardware effects. The decompiled
indirect dispatch and event-source targets remain unresolved, so the
cache-table equality alone cannot establish that Apple display-idle
coordination may safely be omitted.

The iPadOS PMGR transition path also shows the bridge loop after a
state operation when the requested state is `0xf`. The tuner callback
reconstructs state from a separate software bitmap, but the exact
notification-to-bridge ordering remains unproven. Neither finding
justifies running a bridge or MCC write in the current control boot.
Private output is retained as `ios15display-idle-follow.c` and
`ios15display-idle-deps.c` under `artifacts/live/private/gpu-offline/`.


### Comparison with Orchard A9 render driver: 2026-11-05

The Orchard A9 G5P render [PR 74](https://github.com/OrchardLinux/orchard/pull/74)
reports successful J71t rendering on its upstream fork build, while
explicitly noting its exported Orchard image has not been booted. The
PR's transport code, at commit `85adc6e3cad99c73b25c254eb88c07e5b8f8d217`,
requests the GFX domain and performs the same three GPC/Fender wake
writes followed by a bounded poll and delay. Its optional R41 bridge
replay defaults to disabled (`gfx_bridge_replay = 0`). The optional
A9 experiment maps bridge windows at the same two physical base
addresses, but its table offsets, contents and selector indices differ
from J81's. The driver also includes conditional GFX power cycling for
a separately controlled recovery path; that is not a validated J81
sequence.

This supplies evidence that the reported A9 path need not replay those
bridge settings in its default configuration. It does not show what
earlier boot stages configured, prove J81 inherits them, identify why
the J81 read hung, or establish safety of A8X bridge accesses or power
cycles. The Apple G4G predicate's wrapper `+0xc` is a controller-object
software flag, not evidence of an MMIO register at GPC `+0xc`. The
public transport patch is retained privately for reproducible analysis.
