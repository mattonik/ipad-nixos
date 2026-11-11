# J81 page 5: what the LLB clock helper actually checks

Offline instruction-level review of the decrypted J81 iPadOS 15.8.8
(19H422) LLB, load base `0x180380000`. The iOS runtime captures are from
15.8.5 (19H394), so this is a cross-build comparison, not a trace of that
boot. No device access or register writes were performed.

The helper at `0x180391218` operates on a page selected by its first
argument. When its second argument is nonzero it writes encoded fields and
bit 29 to page `+0`, polls `+0` bit 25 until clear, clears bit 0 of `+4`
using a read-modify-write, and polls `+4` bit 31 until clear. It then sets
`+0` bit 31 and again waits for `+0` bit 25 to clear. The `+4` polling
loop is `ldr` at `0x1803912bc` followed by `tbnz` on bit 31 at
`0x1803912c0`. It does not test bit 30; the read-modify-write preserves
the bit in the value written, which does not prove the hardware accepts it.

The three direct calls identified in this LLB pass page indices 1, 3, and
4, not 5. Page 5 has its own earlier setup that polls `+0` bit 25, clears
`+4` bit 0, and sets `+8` bit 24. This is consistent with related register
layouts, but it is not evidence that the helper ran for page 5 or that
the pages have identical hardware semantics. Indirect or other code paths
were not excluded.

In the existing Linux snapshot, `+4` is `0x40000000` for pages 1, 3 and 4,
`0x80000001` for pages 0 and 2, and zero for page 5. This is a useful
observation for comparing the pages, not proof that bit 30 means PLL lock,
clock enable, or GPU readiness. On iOS the page-5 `+4` bit 30 changes
between two marked points in a single instrumented boot; the cause is still
unknown. The iOS page-5 `+0` and `+4` values were sampled in separate
boots, so they are not a simultaneous pair.

The existing [rate calculation analysis](2026-11-10-j81-page5-bit30-rate-analysis.md)
shows that the inspected LLB calculation does not use `+4` bit 30. Taken
together, these results separate a known software poll of bit 31 from the
unexplained bit-30 difference. They do not show which agent changes bit 30,
whether it is writable, or whether it contributes to the Linux core-read
stall. Neither forcing it nor repeating the stalled core read follows from
this analysis.

The next discriminating observation is to capture page-5 `+0` and `+4`
back-to-back at the same iOS checkpoint after GPU identity, using the already
successful read paths. If `+0` bit 31 is clear while `+4` bit 30 is set,
that weakens the idea that bit 30 simply mirrors the enable bit used by
this LLB calculation. A different result warrants checking boot-to-boot
variation; either outcome is only a sampled relationship and does not prove
causation or electrical clock state. Reads are sequential, not atomic, and
instrumentation can perturb timing.

Evidence: Ghidra decompilation and instruction listing of the private LLB
with SHA-256 `493a2a205a7d0fe7161c36d07068c87e93cef70bcc96a1a8519762a8ecf2da46`;
[cross-OS captures](2026-11-10-j81-page5-capture-results.md) and
[LLB clock data flow](2026-11-09-j81-llb-page5-clock-dataflow.md).
