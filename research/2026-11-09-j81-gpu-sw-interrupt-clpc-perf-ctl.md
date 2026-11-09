# GPU software interrupt, CLPC GPU feedback, and the perf control words (2026-11-09)

Offline only. Labels: **E** read in code or data, **I** inference,
**U** unknown. Sources: iPad5,3 12B410 kernelcache (sha256 `19c277d6...`),
the 15G77 (iOS 11.4.1) `ipad5b` kernelcache from the NAS extract, the
15.8.8 LLB, and the saved J81 ADT.

## How iOS 8.1 uses `meta-sw-interrupt`

The only code reference is an `adr` at `0xffffff8003287384` in
`AGXAccelerator::configureDevice` (E). It reads the property, and if it is
longer than `0x27` bytes it takes the second 20-byte record, otherwise the
first. A record is `{u64 set, u64 clear, u32 mask}`, and it is copied to
`this+0x5db0`/`+0x5db8`/`+0x5dc0` (E). J81's property is 40 bytes, so iOS
uses the second record: set `0x20e104010`, clear `0x20e104090`, mask
`0x400`, i.e. AIC software IRQ 138, the last `sgx` interrupt (E). See the
AIC decode in the [15.8.8 scan note](2026-11-09-j81-iboot-15.8.8-first-scan.md).

The two users of those fields:

- `0xffffff800329e270`: when a capability call (vtable `+0x718`) returns
  true, the driver puts `set - 0x20e104000` (`0x10`) and the mask into the
  firmware init block at `+0x1f8`/`+0x1fc` (E). So the GPU firmware gets
  told which AIC software-IRQ bit to set to interrupt the AP (I from the
  values).
- `0xffffff800329f9c0`: in the interrupt path, when the same capability
  holds, the AP writes the mask to its own mapping of AIC `+0x90`
  (SW_CLR), acknowledging the interrupt. Otherwise it clears a word in
  shared memory instead (E).

Both happen after the firmware is loaded. Neither touches the GPU block
before the core-ID read (E for the code shown, I that nothing else uses
the fields: no other `0x5db0`-`0x5dc0` access exists in the AGX range).

## CLPC GPU feedback

The ADT's `sgx` `function-clpc_gpu_feedback` points at phandle `0x1c`
(the `clpc` node) with magic `GPUF` (E). The 12B410 kernelcache has no
`clpc_gpu_feedback` or `gpu_feedback` string and no `GPUF` constant in
code; an indirect or unnamed code path could still use it (U). In 11.4.1 the
`AppleCLPC` side has `AppleCLPCGPUFeedbackFunction`,
`AppleCLPCGPUSampler`, `AppleCLPCGPUFrameTimeMetric` and
`AppleCLPCGPUCommandQueueController` (E, strings). That is runtime
frame-time and queue telemetry for DVFS (I). The strings alone do not
establish when it is used or exclude a pre-ID dependency.

## Who sets `0x20e01c200`/`0x300` on 15.8.8

A further pass over the 15.8.8 LLB for stores at `#0x200`/`#0x300` offsets
found four. None has a PMGR GFX base: `0x180391614` is RMW on the
`0x202230018` CPU-cluster block, and `0x180399e00` is a loop helper for a
controller with registers at `+0x800`/`+0x9a8` (E). So the writer is still
not found (U). The candidates are a path this analysis misses, the
another boot stage, retained state, or reset values.

The live values (`0x80000000`, `0x40000001`) match values written by
8.1 LLB. We have not observed those words at the GPU ID read during a
working iOS boot, so this comparison does not rule out their relevance to
the hang or establish the writer.

## Result

None of the three leads finds a pre-ID step that iOS does and test4
skips. The inspected software IRQ paths occur after firmware loading. The CLPC
usage and perf-control words remain bounded leads, not confirmed causes.
