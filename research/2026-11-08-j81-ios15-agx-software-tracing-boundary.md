# J81 iOS 15 AGX software-tracing boundary

Date: 2026-11-08. Offline inspection of repository artifacts only. No iPad,
kernel patch, build, or external source was used.

## Finding

There is no unmodified software path in the available artifacts that can
observe every direct AGX MMIO access made by native iOS 15 XNU. The A8X/T7001
has no EL2, so m1n1's stage-2 MMIO trapping is unavailable (see
`2026-11-07-a8x-m1n1-hypervisor-feasibility.md`). iOS user-space IOKit hooks
can record user-client method/trap arguments and results, but do not see
kernel-originated MMIO instructions. The local iOS 15 disassembly does show
direct mapped-register accesses in AGX G4G, including GPC writes/polls and
RGX identity reads, but that is static evidence, not a runtime trace (see
`2026-11-07-j81-ios15-g4g-pre-id-mmio-sites.md`).

## New bounded evidence from local artifacts

The local J81 iOS 15 decoded cache (embedded `DTPlatformBuild=19H402`; its
19H422 source IPSW association is verified; see [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md)) is available at
`artifacts/live/private/gpu-offline/ios15-kernel` (SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`). Its
prelink inventory identifies the `gpu,t7001` AGXG4G personality; its
`signature` field is `????`, so this inventory does not identify the
signature format or establish custom-kernel acceptance. The same cache's
disassembly has the two GPC direct-write sites at
`0xfffffff006683980`/`...3988`, an unconditional GPC write and busy poll at
`...3994`–`...39a0`, plus direct RGX loads at `0xfffffff00669bb58` and
`...69bb5c`. Those are candidate instruction sites for a future targeted
instrumentation experiment; the static listing cannot establish whether the
branches run or what the mapped physical base is.

The local AGX personality does not declare an `IOUserClientClass`, and the
existing A10 capture-hook reference only instruments user-client API/trap
calls. Therefore neither the decoded cache nor the user-space hook reference
provides a ready-made kernel MMIO trace facility. No evidence was found in
this task establishing that a stock iOS 15 kernel exposes DTrace/kdebug events
for these specific load/store instructions.

## Viable routes and limits

1. **Offline now:** continue disassembling the exact iOS 15 image, resolve the
   AGX mapping callbacks/vtable slots and call conditions, and produce a
   static list of candidate sites. This needs no device, patch, or build and
   is the only presently viable path under the stated constraints.
2. **Later, targeted runtime logging:** instrument the relevant XNU/AGX code
   before execution (or use a validated kernel debugger to place instruction
   breakpoints) and log a small ring buffer of PC, mapped address, operation,
   and value to a safe sink. This is a separate kernel-instrumentation effort,
   not enabled by the existing user-client hook. It would need an early-boot
   injection method and proof that debug state and memory protections permit
   it on this device/firmware.
3. **Not available:** m1n1's generic all-MMIO tracer. It relies on EL2 stage-2
   translation, absent on T7001; PongoOS/m1n1 running at EL1 cannot intercept
   arbitrary XNU loads/stores in that way.

The normal Apple boot artifact is signed. The checkm8/PongoOS chain can load
custom code, but this repository
does not establish a tested path for booting a modified iOS 15 kernel on J81,
nor that KTRR/PPL/debug policy permits runtime text modification. Treat a
preboot-modified kernel as a research dependency, not an assumed capability.
No signing, KTRR/PPL, DTrace, or debugger behavior was experimentally tested.

## Offline follow-up that can be done without a device or build

- Resolve the iOS 15 `+0x78` mapping callbacks and `+0xa38` dispatch target
  against the same cache, as identified in the pre-ID site inventory.
- Inspect the kernelcache's trace/debug symbol references and AGX call graph
  for existing tracepoints at those exact paths; absence of nearby strings
  alone would not prove absence of instrumentation.
- Record the boot-chain requirements for a hypothetical instrumented image
  separately; do not infer successful custom-XNU boot from PongoOS's ability
  to load unsigned standalone payloads.
