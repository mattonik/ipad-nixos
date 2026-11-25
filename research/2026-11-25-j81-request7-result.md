# Research request 7 result: what else must happen before the Fender `+0x20000 = 0` store (J81, 19H394)

Offline analysis of the stock iPadOS 15.8.5 (19H394) J81 kernel, sha256 `c3507666…a0008`, AGXG4G kext. Addresses drop the `0xfffffff0` prefix. Tags: **code** (read from the disassembly), **adt** (the captured J81 ADT), **capture** (the runner's run log or source in `context/`), **inferred**, **claimed**. No device was used.

The request 6 result proposed the GFX power cycle as the missing step. Run 24 shows that was wrong: the power cycle works, and the store still hangs. This pass looked for anything else, and found one new candidate (below, "Leading hypothesis").

## Findings

**Q1, located (code, strong): `accel slot 0x8a8 (1)` writes no GPU, Fender or PMGR register.** t1 lists every step. It does four things:
- enables a timer event source (`+0xe30`);
- enables two software interrupt event sources (`+0xde8`, `+0xd30`), which have no provider;
- enables three GPU interrupt sources: ADT interrupt indices 1, 0 and 4, which are AIC lines `0x87`, `0x86` and `0x8a`;
- sets the flag `+0xe28`.

Its gate checks are always true on J81:
- accel `+0xe70` bit 8 is set unconditionally by the G4G subclass (`0x66991a0`);
- `(0x7a4d882 & 0x12) != 0x10` holds because J81 uses Fender.

The only hardware effect is the interrupt-controller unmask that `IOInterruptEventSource::enable` performs (inferred from xnu semantics; the calls are code). That is AIC MMIO at `0x20e100000`, not GPU MMIO. No callee arms a timeout or touches a register.

The interrupt path was also decoded (t1, last rows):
- the filter (`0x6672758`) returns 1 and reads nothing;
- the action calls fw slot `0x1f8` (`0x668bba0`);
- that routes indices 1–3 to a Fender handler (Fender slot `0x28`, `0x669901c`), which reads `+0x14` and writes back `value & 7`;
- it routes indices 0 and 4 to the firmware/META handler.

At boot the host has just written Fender `+0x10 = 0` (`enableGPCHostInterrupts(3)`, confirmed to write 0: jump table `0x57c31a0` → `0x6699004`). So no Fender interrupt can fire at the store. Apple turns Fender interrupt bit 0 on only in its idle power-off routine (accel slot `0x8a0`, `0x66736a4`), which the boot path doesn't run.

The Linux runner doesn't request the GPU interrupts, so they stay masked. That is not a register-level difference that could reach Fender's bus.

**Q2, partly located (code for the structure; inferred for the hardware).** Nothing in the kext names a ConfigRAM status register. Fender's register dump (slot `0x40`) names exactly seven registers (t2), and a scan of every Fender-object access in the kext finds no other offset. So there is no "walking/idle" register to poll.

The override register has these uses:
- a plain store of 0 (three callers, request 6 t2);
- a hold: store `0x20`, wait until bit 5 reads 1, then wait for busy clear (slot `0x60` with argument ≠ 0);
- reads in the register dump and in the "Pre-inspection fender snapshot" (`0x669c1a0`).

Two pieces of code evidence tie the walk to the override release rather than to the 0→1 request:
- **(a) In `bootFirmware` the override release takes the place of the final reset release** (t4). Without Fender, `bootFirmware` writes `SOFT_RESET = 0` straight to RGX (`0x669034c`). With Fender it writes `+0x20000 = 0` and then `+0x1000 = 0x11` instead (`0x669036c`–`0x6690394`). So the stream holds the register writes, ending with its own `SOFT_RESET = 0` entry, and the override release is where the host hands them to Fender.
- **(b) Holding the override is how Apple keeps the GPU reachable for direct RGX access.** fw slot `0xd8` (`0x66906d0`) does three things in order before touching META slave-port registers on RGX: it sets the hold (`+0x20000 = 0x20`, waits for bit 5), rewrites `+0 = 0x40000000`, and checks state ≥ 1 (t3).

This fits the runner's own results (capture):
- Run 14: a non-empty list followed by 0→1 without the store completes, and the list is not replayed.
- Run 15: the store hangs in state 1 too.
- Runs 12–19 and 24: the store hangs in state 0 with any non-empty list.
- Run 11: an empty list passes.

What the hardware does during the walk is not visible from host code.

**Q3, located for the kext's use of the bits (code); the PMGR link is inferred.** `+0` is `AGX_CR_FNDR_TIMER_SLEEP_CONTROL`, Fender's sleep timer (t2, t3):
- The host only ever writes `0x40000000` (the probe at `0x668398c`, and Fender slot `0x58` from three callers), plus one value taken from firmware shared memory in the META reset path. No code writes bit 29.
- Bit 29 is a status bit set by something other than the host. The doorbell calls it **SNOOP**: before writing RGX `MTS_SCHEDULE` (`R0 +0xb00`) in state 0, it requires `+0` bit 29 or `+0x14` bit 1, and otherwise logs "About to write MTS_SCHEDULE without SNOOP set!" (`0x6690e70`–`0x6690eb4`).
- `+0 == 0` in state 0 means "uninitialised GPU": the doorbell then runs the full restart `0x668ea90` (stop, gate off, gate on, stream, `bootFirmware`).
- Apple's "can power off" test (Fender slot `0xa0`, `0x669c4a8`) needs bits 29 and 30 both set, state 0, busy clear and `TIMER_KICK_STATUS (+0x8) == 0`.

So bit 30 enables Fender's timer-driven sleep, and bit 29 reads back once Fender has gone to sleep with snoop armed. A later host access to RGX is then caught and wakes the GPU (inferred from these uses; the names are Apple's).

The kext never touches PMGR's PLL5 (`0x5004`, by search). But the runner's observation fits this reading: a PMGR `+0x5004` read works before `+0 = 0x40000000` and hangs after it in state 0 (runs 20–23). If Fender's timer sleep turns PLL5 off on its own once bit 30 is set, its registers would stop answering (inferred, not proven).

**Q4, partly located (code); the walk's own needs are not located.** Nothing in the kext, the ADT `sgx` node or the request 4 firmware tables says what clock or reset state the walk needs for an RGX entry. On the direct path (`gpu_gpc=0`, t4):
- bit 1 of `0x7a4d882` is clear;
- that also clears bit 2 unless bit 3 is set, so there is no first wake, no 1→0 request and no power cycle;
- the same register program is stored straight to RGX by the fw write helpers.

The first RGX write on both paths is `SOFT_RESET (0x100) = 0x00e7fffffffffc1d` (`0x6690c04`–`0x6690c20`). Nothing is written to RGX before it. There is no META/BIF clock enable or other `gpu_gpc`-specific write: the direct path's only clock action is the provider gate (GFX, id 124).

The Linux runner does make direct RGX accesses before the stream, which Apple never does on the Fender path:
- W1 rewrites `META_BOOT`;
- W2a sets `SOFT_RESET`, then clears it.

Both leave the registers at their starting values (capture, `step_w1`, `step_w2a`). So they are an unlikely cause, but they are the last order difference besides timing.

**Q5: the next experiment is below.** It tests the one difference this pass found between Apple's path and the runner's. That difference is the *time* between `+0 = 0x40000000` and the override store.

## Leading hypothesis (inferred, moderate)

**Fender's timer sleep has started by the time the runner releases the override, and the walk can't reach RGX from sleep.** In Apple's path, `+0 = 0x40000000` (t1 of request 6, row 25) is followed only by the stream stores with load-backs, the end marker, a timestamp, `0x8a8 (1)` and the store. That is CPU-speed work, well under a millisecond (inferred from the code; not timed).

The runner spends far longer in the same window. Its steps h6 (`+0`), h7 (the list) and h8 (the store) are separate sysfs calls with host round trips, and h7 adds a 100 ms sleep (capture). That leaves the GPU idle in state 0 with sleep enabled, which is the condition Apple's own "can power off" test looks for.

How this fits the evidence:
- **Empty list (run 11):** passes, because the walk has nothing to write to RGX.
- **Any non-empty list (runs 12–19, 24):** hangs, because the first RGX entry can't complete.
- **Run 15, state 1:** also hangs. The sleep timer is not tied to the performance state, and the GPU was idle there too (inferred).
- **PMGR `+0x5004` read after h6 (runs 20–23):** hangs, if sleep turns PLL5 off.
- **Content, encoding, load-backs, reset framing (runs 16–19):** none of these change anything, because none of them affects sleep.

Not explained: why a sleeping Fender doesn't wake itself to finish its own walk. Holding the override before RGX access (fw slot `0xd8`) suggests the hold, not the release, keeps the GPU awake.

## Q5: next experiment (one variable per boot, empty list first)

**Boot 25: observation only. Empty list, run 11's known-passing sequence, plus three Fender reads.**
1. Before h6 (state 0, `+0` still 0), read `+0x20000` once, at least 1 ms after the previous Fender access.
2. Do h6 (`+0 = 0x40000000`) and h7 (end marker only) as in run 11.
3. At the end of h7, after the existing 100 ms, read `+0` once and `+0x1000` once, separated by ≥1 ms.
4. Continue h8–h11 exactly as run 11. No PMGR `+0x5004` read anywhere after h6.

Apple reads `+0` on every doorbell that finds the GPU in state 0 (`0x6690e48` is reached only then), so these reads follow Apple's own practice (code).

What to expect:
- `+0 = 0x60000000` (bit 29 set) means Fender has gone to timer sleep before the store, which supports the hypothesis.
- `+0 = 0x40000000` weakens it.
- `+0x20000` before h6 gives the override's reset value: if it reads `0x20`, a hold is active from power-up.

**Boot 26: the variable. Only if boot 25 shows bit 29 set.**
- Merge h6, h7 and h8 into one call with no sleep and nothing in between: `+0 = 0x40000000` + load, the h7d entry (`0x00ff3808`, `0x00000000`, each stored then loaded back), the end marker `0xffff0000` + load, then `+0x20000 = 0` + load. This is Apple's order and spacing.
- Then h9 (`0x11`) as before.
- Run it first with the empty list (expect a pass, like run 11), then with the h7d entry.
- Expected if the hypothesis holds: no hang, state 1, and SLC `0x3808` reads `0x00000000` (a no-op entry, so a pass shows up only as "did not hang").

For a visible replay, use h7c's `0x3808 <- 1` on the following boot. Expect `0x3808 = 0x00000001` after the cycle.

If boot 25 shows bit 29 clear, do not run 26. Instead test the remaining order difference: drop W1 and W2a, so there is no direct RGX access before the stream, as on Apple's path.

## Not resolved

- What the hardware does at the override release, and whether the walk starts there or merely becomes possible there. Host code shows only the substitution for `SOFT_RESET = 0`.
- What sets `+0` bit 29, and what the low bits of `+0` mean. The META reset path writes a value from firmware shared memory (`fw +0x358[fw +0x338] + 4`), whose producer was not traced.
- Whether Fender's timer sleep turns off PLL5. The kext never touches PMGR's PLL; the link to the `+0x5004` hang is inferred.
- The override's reset value and the meaning of bit 5 beyond "reads 1 while the hold is in force".
- The exact time Apple spends between `+0 = 0x40000000` and the store. Not measured: no capture of Apple's sequence exists.
- What the META firmware does with Fender. The LDR image was not searched for Fender addresses in this pass.
- Classes of the event-source stubs `0x66b139c`, `0x66b154c` and `0x66b15dc`. They were identified by call shape, not by symbol.

## Files

- `t1-slot-8a8.tsv`: Q1, every step of `accel slot 0x8a8 (1)`, plus the interrupt filter, action and handlers.
- `t2-fender-registers.tsv`: Q2/Q3, every Fender register the kext names or touches, with the bits used.
- `t3-sleep-control-users.tsv`: Q3, every user of `+0` and of the override hold.
- `t4-direct-path.tsv`: Q4, the `gpu_gpc=0` path and the first RGX writes.
- `SHA256SUMS`.
