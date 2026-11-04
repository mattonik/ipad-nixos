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
