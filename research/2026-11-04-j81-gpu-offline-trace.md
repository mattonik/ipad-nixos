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

For comparison, the NAS IPSW's BuildManifest associates J81 with
`kernelcache.release.ipad5b` in iPadOS 15.8.8 (19H422). Its decompressed
kernelcache SHA-256 is
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
The private extracted kernelcache and decoded 8.1 device tree remain under
ignored `artifacts/live/private/gpu-offline/`.

The newer kernelcache separates `com.apple.AGXG4G`,
`com.apple.AGXFirmwareKextG4G`, `com.apple.driver.ApplePMGR`, and
`com.apple.driver.AppleT7001PMGR`. Its `AGXG4G_A0` personality matches
`gpu,t7001` on `AppleARMIODevice`; its `AppleT7001PMGR` personality matches
`pmgr1,t7001`, the compatible in the separately captured J81 ADT. This is
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

In 19H422 `AGXG4G`, the G4G Fender performance-state setter at
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
branch; it does not follow that they are irrelevant to other loaders. Its
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
