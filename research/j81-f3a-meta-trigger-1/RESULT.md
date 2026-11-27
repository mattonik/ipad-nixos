# Research request 23 result: the MTS-to-META trigger, RGX 0xb10/0xb20, and the DM0 gate (J81, 19H394)

Sources:
- the J81 19H394 META firmware, expanded with Orchard's `minim.py` as in request 22. The output stays private;
- upstream `pvr_rogue_cr_defs.h` / `pvr_rogue_meta.h`;
- the AGXG4G kext;
- run 74.

Tags: **fwdis**, **code**, **source**, **capture**, **inferred**. There is no firmware or kext content beyond addresses, offsets, field names and small constants. The `minim.py` decode is provisional.

## Short answer

- **The firmware side of the trigger path is complete, and the gate passes with blob f.** With both true, the most likely reading of run 74 is that **thread 0 never receives trigger 5** (inferred).
  - The firmware programs vector `0x04820700 = 5` (external line 0 → trigger 5) and thread-0 TXMASK `0x21` (t1).
  - Before each sleep it clears line 0 in `0x04820010`.
  - Blob f passes every gate input (t3). The type-8 handler then advances the consumer through the common tail. So a pass that ran would have moved the consumer, and the consumer stayed 0.
- **`0xb10 = 0x10` is the MTS holding the presented task** (DM0, counted: the kick word). The firmware only reads it, after a wake, and a host read doesn't clear it. `0xba8` not counting and `0xbc8` ignoring host writes point to the MTS presenting the task without raising META's line, or META not latching it (inferred).
- **There's no host route to META's trigger except the MTS.** The trigger block is reachable only through the slave port, which stalls under E1. No RGX register exposes META's PC.

  Instead, **L1** uses a register the firmware rewrites on every pass: `0xb08`, which it zeroes before each sleep, as a liveness marker. Its first wake may take seconds, because the firmware doesn't arm its thread timer before the first sleep.
- **Correction to request 22:** the firmware's `[Rb++#imm]` addressing is pre-increment. The store before each sleep goes to `0x04820010` (line-0 status clear), not `0x04820000`. The timer re-arm goes to `0x04800020` (thread-0 TXTIMER). Checked against upstream: `0x04830000 ++#48` lands on `META_CR_SYSC_JTAG_THREAD`.

## Q1: the trigger path (t1)

Every META trigger register the firmware programs, with PCs, is in t1. In summary:
- external lines 0, 1 and 4 route to triggers 5 (thread 0), 9 and 2 (thread 1);
- TXMASK is `0x21` for thread 0 and `0x204` for thread 1;
- the firmware writes no mask or level register; on META cores without a mask register, programming the vector is the enable (inferred).

RGX `0xad0`/`0xad8` (MSLVIRQENABLE/LEVEL) are the META-to-host interrupt, not this path. Which hardware source drives external line 0 isn't visible in the firmware. That it is the MTS's thread-0 background request is inferred: it's the only line thread 0 listens on besides its timer.

## Q2: why 0xb10 stays 0x10 (t2)

The firmware never writes `0xb10`. A woken firmware reads it, then writes `0xb08 = 0` and clears line 0 before sleeping again. Nothing else acknowledges it. So "stays `0x10`" fits "never woke".

It would also fit "woke and failed the gate", but the gate passes with blob f. The firmware's own self-kick is `0xb00 = 0` (non-counted DM0, at `0x1001f154`).

## Q3: 0xb20 = 0x8010 (t2)

Upstream doesn't define `0xb20`. The firmware reads it only in a status-snapshot helper:
- bits 5:2 (here 4);
- bit 0 (here 0);
- alongside RGX `0x130` (EVENT_STATUS).

It's set before any kick and never written by either side. It's a hardware reset value or a wrapper status, and nothing indicates we should change it (inferred).

## Q4: the gate (t3)

- POLICY `+8 <= 1`.
- Word 0 of the `0x28` object = 0.
- `0x1000374c` = 0, which needs three per-DM busy words to be 0: root `+0x64` block `+0x830`, root `+0x68` block `+0x77c` and root `+0x6c` block `+0x75c`.
- priv `+0x170` bit 1 clear.

Blob f satisfies all of them (please confirm the three busy words read 0).

**Thread 1 is not needed for DM0.** The firmware starts it itself (`0x10022620`, from config `+0x2f0`/`+0x2f4`), from inside its command-stream interpreter, gated on root bytes `+0x498`/`+0x49a`.

## Q5: does anything else wake thread 0?

Only the thread timer (trigger 0). That timer is META's own TXTIMER, not the AIC page. The AIC timebase is used only for timestamps: `0x100228a0` reads it together with RGX TIMER `0x160`.

The loop re-arms TXTIMER only after a timer wake, so the first tick comes whenever the free-running counter next overflows. That can be several seconds and depends on the META clock (inferred). A 3 s window can miss it. The run-57 hot PC `0x80009c74` lies on the timer-wake path, so ticks do arrive eventually.

A timer wake alone doesn't run the DM pass: with TXSTAT = 1 the loop goes straight back to sleep. Only a latched trigger 5 leads to `0xb10` and the pass.

## Q6: next boots (t4)

1. **L1:** the host writes `0xb08 = 2` (the firmware's own value) after alive, reads it back, then polls it for 30 s. Back to 0 means thread 0 is alive and cycling.
2. **P3:** kick with `0xb00 = 0x00` (non-counted, the firmware's self-kick value). Read `0xb10`, `0xba0`, `0xba8` and the consumer.
3. **K2:** L1, then P3 once L1 proves the firmware is cycling.

Skipped: sampling the PC without the slave port (no such register), starting thread 1 (not needed), and any host trigger write (none outside the MTS).

## Not resolved

- What drives external line 0 in hardware, and why the MTS's presented task (`0xb10 = 0x10`) doesn't raise it.
- The meaning of `0xb20` beyond the firmware's snapshot fields.
- The META clock, and so the first timer-tick delay.

## Files

- `t1-trigger-path.tsv`: Q1, every META trigger register the firmware programs, with values, PCs and names.
- `t2-mts-registers.tsv`: Q2/Q3, `0xb10`, `0xb08`, `0xb20`, `0xba8`, `0xbc8` and the self-kick.
- `t3-gate.tsv`: Q4, the gate inputs, the type-8 handler and thread 1.
- `t4-next-boots.tsv`: Q6, the ranked boots.
- `SHA256SUMS`.
