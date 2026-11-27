# Research request 26 result: a working Orchard boot against our J81 boot: clocks, PMGR and the firmware's timer

Sources:
- Orchard's public A8/A8X/A9 docs in `context/orchard-public`;
- the 19H394 AGXG4G kext;
- the decoded META firmware (private, provisional);
- upstream `metag_regs.h` / `pvr_rogue_meta.h` / `pvr_rogue_cr_defs.h`;
- the run notes.

Tags: **orchard**, **code**, **fwdis**, **source**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **The firmware's own timer is set up correctly, and armed before the loop.** Its 30 s silence means META's clock isn't running (inferred). It isn't a timer setting (t2):
  - TXDIVTIME = 1;
  - TXTIMER is armed at init (`0x10020a38`). Request 23 said it wasn't; that was wrong;
  - the period comes from config `+0x2a8`, the perf table's state-1 MHz (365 in blob f), which gives about a 1 ms tick.

  A stopped GPU or META clock after the firmware goes idle explains all three symptoms at once: no timer tick, no MTS wake, and no slave-port service.
- **The likeliest cause is clock gating** (t3), inferred:
  - our boot has MISC_ACG (global automatic clock gating) on, as iOS does;
  - the garten reports idle under META's control (`0xb50` IDLE_CTRL = META);
  - Fender's snoop bit (`+0` bit 29) reads clear.

  With all three, an idle GPU could be clock-gated with no armed wake source. On iOS the wake is a kick caught by the Fender (TIMER_KICK_STATUS) or the firmware's park/wake path.
- **We haven't yet read whether the GPU clock stays on after alive.** All our PMGR/PLL reads were at h11, before the firmware ran. **C1** (t4) reads PS_GFX actual state, PLL lock, CLK_STATUS and the Fender sleep/kick registers after alive and around the kick. Every one of those reads is already proven safe in state 1.
- **Against Orchard's iOS-order PMGR list** (t1), our boot may lack the PLL1/PLL4 `+8` bits, the `P+0x22000` power-gate words and the voltage-manager enable. Orchard found none of them needed for the ID read, and their effect on the firmware's clock is untested. Fender `+0x10 = 0` already matches Apple, so request 25's F1 isn't needed.

## Q1: the boot timeline (t1)

Twelve steps of Orchard's documented working A8 sequence (iOS PMGR order), each marked done, not known, or a step that differs. The A9 docs here give no register-level PMGR list beyond the A8 one.

## Q2: what makes the timer tick (t2)

META's own TXTIMER, armed by the firmware. Neither Apple's host nor Orchard programs a timer or interrupt path into META; the AIC lines carry interrupts from the firmware to the host only. The A9's "~290 alive a second" is its scheduler pass rate; J81 posts alive once per loop entry, so the numbers don't compare.

## Q3: clock gating (t3)

- RGX CLK_CTRL has no META field.
- META's TXCLKCTRL (`0x048000b0`, ALL_ON / ALL_AUTO) is written by neither the host nor the firmware, and is reachable only through the slave port.
- What can gate the idle GPU: PMGR MISC_ACG / PS_GFX auto states, with the garten's META-driven idle signal and Fender's sleep timer (inferred).

## Q4: the SoC side

The PMGR registers Apple's iOS boot programs (from Orchard's A8 reading) are listed in t1:
- MISC_ACG, SOC_TVM, PLL1/PLL4, the `P+0x22000` block and the voltage manager;
- the DVFS request word `P+0x1c200`, whose state-1 table works on our boot (the PLL locks at h11);
- the PS_GFX layout: bits 3:0 target, 7:4 actual (`0xf` on, 4 clock-gated), 19:16 minimum, 27:24 auto state, 28 auto enable.

I didn't re-read the ADT `gfx`/`pmgr` perf properties beyond request 18's perf table.

## Q5: next boots (t4)

1. **C1 (read-only):** read the clock state after alive, at 1/5/30 s, and right after the kick.
2. **C2:** only if C1 shows the GPU clock gated. Set PS_GFX minimum state to `0xf` before boot.
3. **C3:** last, and high risk. Clear MISC_ACG after the PLL locks.
4. **N3:** CONTROL `+0x20 = 1`, as before.

To confirm a wake: the DC consumer reaches 1, `0xb10` is consumed, MSLVCTRL1 READY rises, `0xac8` bit 2 sets, or new event records appear.

## Not resolved

- Which clock actually stops: PS_GFX auto, MISC_ACG, the Fender sleep timer, or META's internal TXCLKCTRL. C1 narrows it.
- The voltage-manager and PLL1/PLL4 state on our boot.

## Files

- `t1-boot-diff.tsv`: Q1, the working boot step by step against ours.
- `t2-timer.tsv`: Q2, the timer setup and what drives the tick.
- `t3-clocks.tsv`: Q3, the clock-gating registers and who writes them.
- `t4-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
