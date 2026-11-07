# Cascadia GPU methods relevant to J81

Read-only comparison of Project Cascadia's public A5 SGX543MP2 GPU research
with the local A8X/T7001 GXA6850 investigation. No device was accessed.

## Methods worth carrying over

1. **Trace readiness before attempting a register read.** Cascadia's research
   records that the SGX master bank answered after power-up, while core banks
   hung until clock setup; reads from a broadcast bank also hung. It corrected
   the earlier “clock dead end” hypothesis by separating power, master, and
   core readiness checks. For J81, this supports tracing the full Apple
   pre-read wake/reset path and gating each observation on an explicit state
   checkpoint. Local evidence already shows PMGR acquisition succeeds, GPC
   state stays zero, and a direct RGX read hangs; see
   [`2026-11-06-j81-gpu-core-hang-analysis.md`](2026-11-06-j81-gpu-core-hang-analysis.md)
   and [`2026-11-04-j81-gpu-offline-trace.md`](2026-11-04-j81-gpu-offline-trace.md).
   Cascadia's SGX addresses and sequence are not a J81 recipe.

2. **Reconstruct Apple setup, then compare a minimal implementation against
   it.** Cascadia traced iOS `initSGX`, correlated returned IDs/revision with
   ADT expectations, and compared its USSE/PDS/frame setup word-by-word with
   iOS for the same simple quad. This is a useful validation method for the
   local G4G work: keep Apple's and Linux's object/address models explicit,
   simulate host operations without MMIO, and only advance when the
   comparison has no unresolved mappings or ownership. The local inspector,
   host plan, Apple/Linux comparison, and simulator are summarized in
   [`2026-11-06-j81-gpu-morning-runbook.md`](2026-11-06-j81-gpu-morning-runbook.md).
   SGX command buffers, USSE/PDS programs, and firmware ABI do not transfer to
   G4G.

3. **Later-stage hypothesis: shared-buffer cache and translation attributes
   may explain a live-but-stalled firmware interface.** Cascadia found that
   its SGX microkernel was alive and receiving kicks, yet did not consume CCB
   work because shared-buffer PTEs lacked the expected cache/protection
   attributes. After correcting them, commands completed. This motivates
   including cacheability, access attributes, and lifetime in the J81 G4G
   shared-memory audit, alongside address translation. It is only a hypothesis
   for G4G; no A8X evidence currently establishes the required attributes or
   connects them to the observed hang. Do not copy SGX-specific PTE bits.

## Limits

Cascadia's working GPU is Imagination SGX543MP2 (SGX); J81's GXA6850 is a
G4G/Rogue-generation GPU with a different firmware and host interface. The
transfer is investigative method and validation discipline, not register
addresses, initialization writes, command formats, firmware, or driver code.
The local J81 analysis specifically warns that a successful GPC state read
alone does not prove the RGX wrapper is ready.

## Public primary sources

- [Cascadia P105 GPU research notebook](https://github.com/rzxvx/Project-Cascadia/blob/main/devices/a5/docs/research/p105-gpu.md) — readiness sequence, corrected failure analysis, and shared-buffer attribute debugging.
- [Cascadia GPU architecture and implementation](https://github.com/rzxvx/Project-Cascadia/blob/main/devices/a5/docs/GPU.md) — Apple microkernel, own userspace programs, and iOS comparison method.
