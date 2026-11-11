# A9 GPU research: relevance to J81 G4G

Reviewed [brkosebay/a9-gpu-research](https://github.com/brkosebay/a9-gpu-research)
at commit `a20e50767bfb8f18434572cdcdca88465d12d2a8` on 2026-11-11. The
repository describes device-verified A9/G5P acceleration, including Mesa and
a rendered triangle. The author explicitly says the A8/A8X material in the
porting guide is extrapolation: they did not analyze A8/A8X firmware or kexts.
An A9 finding is a hypothesis to check against J81, not a J81 register
contract.

## Findings relevant now

- The [A9 first-triangle guide](https://github.com/brkosebay/a9-gpu-research/blob/a20e50767bfb8f18434572cdcdca88465d12d2a8/FIRST-TRIANGLE.md)
  reports the same early failure: GFX PMGR active but first GPU core read
  wedges; after the A9 Fender initialization, the A9 ID read succeeds. Its
  three Fender writes, poll and 10 µs wait agree with the already-inspected
  J81 iOS path. Our J81 Linux tests reached state 1 and reported control
  `0x40000000` but the core read did not complete. This is not a new J81
  solution and does not justify repeating the failed read by itself.
- The A9 runtime accessibility predicate checks Fender power, a nonzero GPC
  state within the supported range, and control bit 29 clear. J81's Linux
  state 1/control `0x40000000` is consistent with those raw A9 checks on the
  measured boot, but the live J81 predicate, maximum state and timing are not
  proven equivalent. Passing analogous checks is not evidence that J81 R0 is
  accessible. The A9 report that R1 reads are safe under its PMGR conditions
  is not a blanket safety claim for J81.
- The [A9 power note](https://github.com/brkosebay/a9-gpu-research/blob/a20e50767bfb8f18434572cdcdca88465d12d2a8/docs/power/oc-opt1-20261110.md)
  describes GPU performance records with voltage and PLL fields, but explicitly
  says that a kernel-side PLL lock/frequency readback was not known on A9 and
  that actual PMIC voltage was not measured. This is useful context for the
  current DWI hypothesis, not proof that J81 PMGR `0x5004` is a GPU PLL lock
  or that the candidate J81 PMU row is a GPU rail.
- The A9 reset FIFO, META loading, command queues and Mesa path are valuable
  reference material **after** J81 core access works. Their mode bits, FIFO
  words, firmware layout and shader ISA must be re-derived on G4G; do not
  replay A9 values as a J81 wake fix. The guide reports a second A9 hard lock
  when core registers were read while reset was held.

## Tools checked on the actual 19H394 input

The [published firmware tools](https://github.com/brkosebay/a9-gpu-research/tree/a20e50767bfb8f18434572cdcdca88465d12d2a8/tools)
are MIT licensed and operate locally. The `--list` command successfully
found `com.apple.AGXG4G`, `com.apple.AGXFirmwareKextG4G` and
`com.apple.iokit.IOAcceleratorFamily2` in our 19H394 prelinked cache.
The top-level extraction stopped because it unconditionally expects
`com.apple.iokit.IOGPUFamily`, absent in this input. It had already extracted
the two G4G kexts before stopping, but produced no complete manifest; partial
outputs must not be treated as a successful full extraction.

Invoking the published `decode_ldr` function directly on the extracted
G4G firmware kext `__TEXT,__const` section succeeded: it identified a META LDR
and decoded 88 records (67 load, 13 zero, 5 comment, 2 config, 1 thread-start).
The companion reconstruction script produced five region files. These are
useful offline analysis inputs and corroborate the earlier iOS 8.1 META
finding; they do not show that this section is the runtime image without the
independent kext ownership check, validate LDR checksums, establish that the
reconstructed image executes, or enable Linux access to the core. No META
objdump was available locally, so no firmware instructions were disassembled.
The generated Apple-derived files remain private under
`artifacts/live/private/a9tools-j81-19h394/`.

Next offline work is to check the G4G firmware-return path and cross-validate
these records against our existing parser, then assess the published META
binutils/MINIM tools. In parallel, the DWI-first voltage comparison remains the
most direct currently proposed hardware test; this A9 repository supplies no
measured J81 DWI or GPU-rail evidence.
