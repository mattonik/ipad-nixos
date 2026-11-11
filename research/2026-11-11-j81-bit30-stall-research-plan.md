# J81 GPU stall and page-5 bit 30: discriminating research plan

## Questions and current boundaries

1. Does iPadOS write the page-5 word during the observed transition, or is
   it changed by another agent or hardware? **Unresolved.** In the 19H394
   instrumented boot, `+4` was zero before the GPC request and
   `0x40000000` after its poll. The original same-thread instructions between
   these boundaries contain a GPC store and poll, but interrupts, other CPUs,
   firmware, read effects and autonomous hardware remain possible. The
   existing [writer trace](2026-11-11-j81-ios-page5writer-result.md) has a
   positive site control but cannot exclude a delayed writer, other store
   sites, address aliases or hardware.
2. Why did Linux fail to complete the GPU identity read? **Unresolved.**
   The last 20-domain test reached an acknowledged before-read checkpoint
   with PMGR `0x3ff`, GPC state `1`, and GPC control `0x40000000`, but no
   completion. The checkpoint is before the load; it does not prove exactly
   where execution stopped or which hardware component caused it. DWI and
   restored domains alone were insufficient in that experiment.
3. Are the compared device addresses and setup tables wrong? A new
   [live iOS IORegistry cross-check](2026-11-11-j81-ios-live-resource-crosscheck.md)
   independently corroborates the core/GPC/PMGR resource order and the
   two 264-byte bridge configuration tables. It does not measure live PTE
   attributes or prove register stores were accepted or retained.
4. Is bit 30 a prerequisite for GPU access? **Unresolved.** Its value differs
   between measured iOS and Linux checkpoints, but neither causation nor
   writability is known. The same-checkpoint iOS pair shows it can be set
   while the adjacent `+0` bit 31 is clear.

## Work in priority order

### 1. Identify an actual iOS store or bound the search

Audit the ordinary PMGR `+0x980` read path to resolve the effective virtual
address used for page 5, then audit all CPU store paths that could reach that
mapping. Extend the existing store trace only after checking exact 19H394
instructions and displaced-instruction correctness. Include the ordinary
PMGR store and, if feasible, the distinct bridge store; compare effective
addresses internally without logging kernel pointers. Record write value,
site, thread/phase association, entry, completion, overflow and explicit
window boundaries in a bounded buffer; emit only at an established safe
later checkpoint. Include a positive control that exercises the comparison
and export path and a control confirming each instrumented site executes.

Host-test exact signatures, unsupported kernels, register/flag preservation,
reentry, buffer overflow, concurrent producers and boundaries. A matching
completed store gives a concrete writer to trace. No match only narrows the
instrumented sites, widths, address mapping and observation window. In-flight
counters cannot rule out a CPU paused before entering a trampoline or before
the counter update; aliasing, untraced stores, firmware and hardware remain
possible. A synthetic record proves instrumentation plumbing, not that a
real target write was covered. If these limitations prevent a useful
conclusion, stop and pick a different discriminator rather than spend a DFU
cycle on a negative result.

### 2. Compare a concrete pre-identity prerequisite

Trace any observed writer back to its provider/caller and identify the
operation's inputs and side effects before proposing a Linux experiment.
If no usable writer emerges, focus on platform clock and provider state:
compare actual iOS provider operations and runtime values with Linux at
equivalent GFX/GPC boundaries. Select a register only when its source,
address, read semantics, and possible side effects are understood well
enough for an informative comparison. Existing software checkpoints do not
prove bridge-store completion; do not equate the matching tables with
matching hardware state.

### 3. Test one supported difference and retain recovery evidence

Only after a specific missing operation or state is established, design a
fresh-boot, one-variable Linux test with pre/post controls, explicit host
checkpoints and watchdog, and a defined result for success, mismatch and
timeout. A later single GPU identity read is a separate risky endpoint after
the control has demonstrated the intended state. An unchanged bit or a
non-return is not by itself a diagnosis; the before-read handshake does not
prove the load was reached. A guessed page-5 write or bulk bridge read is
not justified by the present evidence.

## Independent comparison

[A9 research](https://github.com/brkosebay/a9-gpu-research/blob/a20e50767bfb8f18434572cdcdca88465d12d2a8/FIRST-TRIANGLE.md)
reports a similar active-power-domain core freeze solved by Fender/GPC setup;
J81 already exercised the analogous sequence without completing the read.
That supports investigating additional prerequisites, not copying later A9
firmware/reset steps or naming page-5 bit 30 a PLL lock. No complete J81
fix is established by the cross-device comparison.
