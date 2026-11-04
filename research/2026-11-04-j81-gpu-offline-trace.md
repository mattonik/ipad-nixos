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

The Fender-like `reg[1]` mapping, any required performance-state write,
provider identity at the power call, and the order of the first RGX access
are not yet established. In particular, the clock/power calls above must not
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

The next offline task is to trace the pre-power virtual callback and the
provider's exact gate/error behavior, then design a bounded test and recovery
procedure. These writes and waits can hang or affect the GPU, so the proposed
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
