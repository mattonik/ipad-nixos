# Research request 27 result: META's clock, CLK_STATUS 0x00600000 and the wake path (J81, 19H394)

Sources:
- upstream `pvr_rogue_cr_defs.h`, `pvr_rogue_meta.h` and `metag_regs.h`;
- the decoded META firmware (private, provisional);
- the 19H394 kext;
- our LDR boot list;
- run 79.

Tags: **source**, **fwdis**, **code**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **META's clock is running** (t1, t2):
  - CLK_STATUS `0x00600000` means SIDEKICK and BIF_SIDEKICK are RUNNING and every other unit is idle-gated: a normal idle GPU with the META/garten domain clocked.
  - META's own TXCLKCTRL resets to DEFON (always on). Nobody writes it: not the host, not the firmware (neither by address nor by a move into the register), and not the LDR boot list.
- **The 30 s silence is by design, not a stopped clock.** After a ring scan finds no TA/3D/CL work, the firmware masks its own timer (`0x1001fea8`: TXMASK = `0x20`, kick-state `+248 = 1`). It unmasks it when work appears. So an idle firmware waits for MTS line 0 alone. Request 26's "META clock stopped" is withdrawn; MISC_ACG is off the hook too.
- **Everything still comes down to line 0 never firing.** On the firmware side the routing is complete: DM0 background goes to thread 0 (`0xb30` bit 0), vector `0x04820700 = 5`, and TXMASK bit 5 is set. There's nothing more META-side to write (t3).

  The firmware's own self-kicks are **non-counted**: `0xb00 = 0`/`1`/`2` for TA/3D/CL, from that ring scan. Our host has only tried counted kicks (`0x10`, `0x30`).
- **The pending slave-port request is a wake detector.** It completes (READY rises) only when thread 0 runs. **W1** pairs it with the firmware's own kick value, `0xb00 = 0x00000000`.

## Q1: CLK_STATUS (t1)

Bits 22/21 are SIDEKICK/BIF_SIDEKICK running; the other units are gated. An idle iOS GPU after alive should read the same (inferred). CLK_CTRL `0x0000` bits 45:44 hold the sidekick domain's mode. The firmware writes CLK_CTRL itself; a read-only check is R in t5.

## Q2: META clock gating (t2)

TXCLKCTRL fields cover the execution units and caches (A0, A1, D0, D1, FP, DC, IC); each is OFF, DEFON or AUTO, and the reset is DEFON. Its fields don't name the timer or the trigger logic (inferred). A slave-port request to a thread blocked in its TXSTAT wait stays pending until the thread wakes (inferred, consistent with runs 74–79).

## Q3: the wake path (t3)

- DM associations: background for every DM except DM5 goes to thread 0; interrupt context for every DM goes to thread 0.
- `0xb58`–`0xb80` route GPU event bits to interrupt-context tasks, which isn't the kick path.
- The lines: 0 → trigger 5 (thread 0), 1 → 9 and 4 → 2 (thread 1), plus thread 0's timer, which is masked when idle.

Which hardware signal drives line 0 isn't visible.

## Q4: host control of META's clock (t4)

There's no need: it's DEFON.
- **(a)** A slave-port TXCLKCTRL write is possible but would change nothing.
- **(b)** The LDR boot list (12 segment-MMU tuples and 27 CONFIG writes, listed in t4) contains no clock or trigger register, and ours is Apple's.
- **(c)** RGX CLK_CTRL SIDEKICK = ON would force the domain on, but it's already running.

## Q5: next boots (t5)

1. **W1:** with the pending slave-port read as the detector, kick with `0xb00 = 0x00000000` (non-counted DM0). Watch READY, `0xb10`, `0xba0`, the DC consumer and `0xac8`.
2. **W2:** the same with `0x00000001`, then `0x00000002`.
3. **R:** read CLK_CTRL.
4. **W3:** the detector with the usual counted kick.

To confirm a wake: READY rises, `0xb10` goes to 0, the DC consumer reaches 1, `0xac8` bit 2 sets.

## Not resolved

- The hardware source of META external line 0, and why a presented MTS task doesn't raise it.
- The meaning of the boot list's `0x03000000`/`0x04700000`/`0x040000c0` words.

## Files

- `t1-clk-status.tsv`: Q1, the CLK_STATUS bit decode and the CLK_CTRL sidekick field.
- `t2-meta-clock.tsv`: Q2, TXCLKCTRL, the timer mask, the self-kicks and the detector.
- `t3-wake-path.tsv`: Q3, the MTS association and interrupt-enable decode, and the lines.
- `t4-host-clock.tsv`: Q4, the three host options and the LDR boot list.
- `t5-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
