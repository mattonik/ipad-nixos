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

Target-specific 15.8.8 G4G driver strings explicitly identify the second
register block as GPC/Fender terminology, including `AGXFenderCommon`'s
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
