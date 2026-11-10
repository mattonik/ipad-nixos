# J81 page-5 bit 30 and the bootloader rate calculation

Offline comparison on 2026-11-10 of the paired iPadOS capture, Linux samples,
and the existing disassembly of the J81 15.8.8 (19H422) LLB. No device
access. The iOS capture used 15.8.5 (19H394); the LLB analysis is cross-build
static evidence, not a trace of the tested boot.

The paired iOS PMGR-method reads at region 0, offset `0x5004`, instance 0
returned `0` and `0x40000000`, respectively after the clock-provider return
and after GPU identity. The Linux post-GPC sample returned `0` on another
boot. The association with physical `0x20e005004` comes from the captured
Pongo ADT; the runtime iOS physical mapping is not independently verified.

The LLB rate loop at `0x18039098c`–`0x1803909d0` reads page `+0` and `+4`.
When `+0` bit 31 is clear, instructions `sbfx w12,w13,#0,#1` and
`and w12,w12,w23` use **only bit 0** of `+4`: the computed rate is 24 MHz
if bit 0 is one, otherwise zero. When `+0` bit 31 is set, the alternate
calculation uses fields of `+0` and `+8` and does not use `+4`. Thus neither
branch of this specific calculation consumes `+4` bit 30.

Consequently, toggling bit 30 alone cannot change the calculated page-5
rate in this loop. In the separate iOS and Linux samples, `+0` was `0x1010`
and bit 0 of `+4` was clear, which would select a zero *calculated* rate if
those values were simultaneously supplied to this LLB calculation. They
were captured on separate boots and at different points, so this is a
conditional calculation, not an observed boot-time rate. It says nothing
about physical clock state. The prior bounded LLB selector-table analysis
also found no direct use of page-5 rate slot 6 in its scanned entries; see
[the data-flow trace](2026-11-09-j81-llb-page5-clock-dataflow.md).

This lowers the priority of interpreting bit 30 as a direct input to that
LLB rate calculation. It does not identify the bit, rule out another
software or hardware consumer, prove causality, or justify a write. The
proposed [GPC-poll intermediate sample](2026-11-10-j81-page5-transition-next-boundary.md)
would narrow timing but would not alone establish whether this bit matters
to the Linux identity stall. Investigating the actual clock/power provider
and its runtime state remains a separate, higher-value route.

Evidence: private disassembly
`artifacts/live/private/ghidra-iboot/insn_15llb_page5_consumers.txt` and
[the captured samples](2026-11-10-j81-page5-capture-results.md).
