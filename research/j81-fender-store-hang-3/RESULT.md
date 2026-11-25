# Research request 8 result: what else must exist for the Fender ConfigRAM walk / `+0x20000` store (J81, 19H394)

Offline analysis of the stock iPadOS 15.8.5 (19H394) J81 kernelcache, sha256 `c3507666…a0008`. Requests 6 and 7 looked only at the AGXG4G kext. This pass also disassembled the PMGR drivers in the same kernelcache:
- `com.apple.driver.ApplePMGR` (text `0x6bb9000`, size `0x34a4c`);
- `com.apple.driver.AppleT7001PMGR`, which also contains the AppleT7000PMGR class (`0x6c88000`, size `0x2f28`);
- `com.apple.driver.AppleARMPlatform` (`0x5b22000`).

Addresses drop the `0xfffffff0` prefix. Tags: **code**, **adt** (the captured J81 ADT), **capture** (the run log or driver source in `context/`), **inferred**. No device was used. The reply contains no Apple binary content beyond addresses, offsets, short mnemonics and field names.

Request 7's sleep-timer lead is dropped. Runs 25b and 26 contradict it.

## Findings

**Q1, located (code, strong for Apple's side): one new difference.** Apple turns the GFX domain on with `AUTO_PM_EN` set. The runner turns it on with that bit clear. Every other difference was already known (t1).

How Apple does it:
- ApplePMGR's set-PS routine (`0x6bc6ed8`) writes the target state into bits 3:0 of the device's PS register and polls until the actual state in bits 7:4 matches.
- If its auto argument is 1, it then sets bit 28 and writes the register again (`0x6bc733c`–`0x6bc735c`). Bit 28 is `AUTO_PM_EN`; the driver's own dump prints the register as "MANUAL_PS=%d, AUTO_PM_EN=%s".
- The device-on callers pass auto = (device flags & 4) == 0 (`0x6bcd4a0`–`0x6bcd4bc`, `0x6bd8770`–`0x6bd8794`, `0x6bc2a44`).

The ADT `pmgr` `devices` entry for GFX has flags `0x00` (adt). So Apple's GFX-on sets `AUTO_PM_EN`. The entry also confirms the register Linux uses: id `0x7c`, PS group 3, index 4, which is `PMGR +0x20300 + 4·8 = 0x20e020320` (`PM_GFX_PS`).

The runner reads `0x3ff` there at every observation point (capture): target `0xf`, actual `0xf`, status bits 8–9 set, bit 28 clear.

Not traced: the exact ApplePMGR caller that the AGX provider calls reach (`+0x568`/`+0x570` at `0x6683920`/`0x668393c` and `0x6692720`/`0x669274c`). Both device-on paths found use the same auto rule, so the conclusion holds whichever one it is (inferred).

The other differences (t1) are known from requests 6 and 7:
- Apple's GFX power cycle (already tried in run 24);
- the interrupt-controller unmask (touches no GPU register);
- a second, identical `+0x10 = 0`.

The runner, unlike Apple:
- writes RGX directly before the stream (W1 `META_BOOT` rewrite, W2a `SOFT_RESET` set and clear);
- reads PMGR during the window;
- reads Fender between `+0` and the store;
- adds host round trips and sleeps;
- stores the override without a load-back (Apple loads it back, `0x669c264`).

**Q2, partly located.** No timer is armed in this window: not by the AGX kext (request 7) and not by any PMGR driver path found. ApplePMGR does have per-device idle mechanisms:
- `AUTO_PM_EN` with an auto minimum level (`_setPSAutoMinLevel`);
- power-gate sleep depth (`PWR_x_CFG0 SLEEP_DEPTH`);
- auto clock gating;
- "no wakeup" (bit 10, `0x6bce9fc`);
- "force no access".

PMGR's hardware auto power-down can't be what goes wrong in the runner, because `AUTO_PM_EN` is clear there (PS = `0x3ff`, capture). The runner's GFX domain is held on manually.

The "time-sensitive empty list" also rests on one run. Run 25b changed two things at once: two Fender reads were added, and the extra 100 ms. So it isn't yet established that elapsed time is what matters (capture). Nothing in the code located a mechanism that would make Fender unreachable after idle time with auto-PM off.

**Q3, located for Apple's reads (code).** Apple reads `+0x20000` in three places (t3):
- the "Pre-inspection fender snapshot" (Fender slot `0x48`, `0x669c1a0`), only when the Fender object is marked powered (`+0xc`, `0x669c190`);
- the full register dump (slot `0x40`, `0x669bd24`), with no guard, used in failure reports;
- the load-back right after its own store (slot `0x60`).

On the boot path, Apple never reads the override before writing it. That matches run 25: the read hangs.

Apple never reads PMGR `+0x5004`: there is no access to that offset in AGXG4G, ApplePMGR, AppleT7001PMGR/AppleT7000PMGR or AppleARMPlatform (code, by search). AppleT7000PMGR's PLL-area code uses `0x5008`, `0x5018`, … `0x5078` (stride `0x10`). So `+0x5004` is the second word of the first PLL block, not obviously "PLL5" (inferred; the runner's name for it should be checked).

Why either read hangs is not visible in host code.

**Q4, not located (code, by search).** No AGX or PMGR code raises a GPU PLL, or any clock for RGX, before state 1. The only host action on GFX before the stream is the PS/provider power-on, now known to include `AUTO_PM_EN`.

On Apple's Fender path, nothing reads or writes RGX directly between the first wake and `waitForFWAlive` (requests 6/7). So Apple doesn't need RGX reachable from the host in state 0; only the walk touches RGX there. The runner's PLL observation (bit 30 set only after 0→1) is consistent with the clock coming from Fender or hardware rather than from the host (inferred).

## Leading candidate (inferred, moderate)

**With `AUTO_PM_EN` set, PMGR follows the GFX block's own power and clock requests. With it clear, as in the runner, those requests are ignored.**

If Fender's walk needs to bring up something through PMGR before its first RGX write (a clock, a power state, or a domain exit from a gated state), PMGR never answers in manual mode, the walk never finishes, and the override store stalls.

How this fits the evidence:
- **Empty list:** nothing to walk, so the store completes.
- **Any non-empty list:** hangs.
- **Run 15, state 1:** also hangs, because PMGR is in manual mode in any state.
- **Apple's GFX power cycle (run 24):** changes nothing, because Linux's genpd power-on also leaves `AUTO_PM_EN` clear.

Not explained: why the 0→1 request itself works and locks the PLL in manual mode. And how Fender actually uses PMGR is not visible from host code.

## Q5: next experiment (one variable per boot, empty list first)

**Boot 27: set `AUTO_PM_EN` on `PM_GFX_PS`, as Apple does, then run run 11's known-passing sequence with an empty list.**
1. After `step_activate` (PS reads `0x3ff`) and before W1, write `PM_GFX_PS = 0x1000000f`. That keeps target `0xf`, sets bit 28, and writes 0 to bits 8–9 and bits 10 and 30, as Apple's set-PS masks them (`0x6bc71c4`).
2. Read PS back once. Expect bit 28 set and actual `0xf`, so `0x100000ff`, or `0x100003ff` if bits 8–9 hold. If bit 28 doesn't read back as set, stop: the variable didn't take.
3. Do nothing that lets Linux rewrite PS afterwards: no `pm_runtime_put`/`get`, no h3p.
4. Then w1, w2a, h0–h11 exactly as run 11 (empty list).

If boot 27 passes, **boot 28** is the same with the h7d one-entry list (`0x3808 ← 0`), then h7c (`0x3808 ← 1`) for a visible replay. Expect state 1 and `0x3808 = 1` after h7c.

**Reads to avoid in all of these:**
- `+0x20000` before it is written (run 25);
- PMGR `+0x5004` after `+0` is written (runs 20–23);
- any RGX read in state 0;
- extra Fender reads between `+0` and the store (keep run 11's spacing).

PMGR PS reads are fine: Apple polls PS itself.

Risk: with `AUTO_PM_EN` set, PMGR may power GFX down while Fender reports idle. A Fender access then might hang where it passed before. Apple runs this way and still accesses Fender in state 0, but Apple may also set an auto minimum level (`_setPSAutoMinLevel`) that this test doesn't reproduce.

If boot 27 hangs before h8, that is itself informative: auto-PM changes Fender's reachability. Report the last step that passed.

**If boot 27/28 do not help:** before any other variable, rerun run 25b *without* its two Fender reads. That shows whether the empty-list store really depends on elapsed time.

## Not resolved

- The exact ApplePMGR entry point the AGX provider calls reach, and whether it also sets the GFX auto minimum level or power-gate sleep depth. The GFX entry lists two further indices (`0x09`, `0x0a`, ADT bytes 28–29) whose table was not identified.
- What `AUTO_PM_EN` makes the hardware do for GFX, and what Fender asks PMGR for during the walk.
- The meaning of PS bit 30 (cleared by set-PS when set, `0x6bc7364`) and of "force no access".
- Why the override read and the PMGR `+0x5004` read hang.
- Whether the runner's `+0x5004` is really PLL5.
- Whether elapsed time in state 0 matters at all (one confounded run).

## Files

- `t1-window-diff.tsv`: Q1, every access in the probe-to-store window that only one side makes.
- `t2-pmgr-ps.tsv`: Q1/Q2, the GFX PMGR entry and the PS register bits as ApplePMGR uses them.
- `t3-reads.tsv`: Q3/Q4, when Apple reads the override, Fender registers and the PMGR PLL area.
- `SHA256SUMS`.
