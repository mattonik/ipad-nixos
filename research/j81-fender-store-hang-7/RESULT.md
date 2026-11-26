# Research request 12 result: the override store, the walk trigger, and the h12 hang (J81, 19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–11 (sha256 `c3507666…a0008`, AGXG4G).

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **capture**: the run log or the runner source in `context/`;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics and field names.

## Short answer

- **The walk runs at the 0→1 transition; the release isn't needed.** META_BOOT's power-on value is 0: it reads 0 before W1 and at h11 of run 35, whose list had no META_BOOT entry. Runs 38/39 read 1 at h11 without any `+0x20000` store. So Fender applied the list on the state-1 request (capture, strong). Request 4's original reading, "replay at 0→1", was right after all.
- **Apple never releases the override and then reads RGX.**
  - Every release (`+0x20000 = 0`) in the kext is followed immediately by a state request: state 1 at boot, state 0 at stop and recovery.
  - The hold (`0x20`) is taken only before META slave-port access in the GPU restart path.
  - After the boot release, Apple's next step is a sleep waiting for the firmware's alive interrupt, with no RGX read.
  - Apple gates direct RGX access on a check: GPC state ≥ 1 **and** `+0` bit 29 (SNOOP) clear (fw `+0x240`).

  h12's reads right after a state-1 release have no counterpart in Apple's code.
- **Apple's boot release is in state 0 and comes before the state-1 request, with the full reset list in ConfigRAM** (code). The runner does the same thing, and that hangs for every non-plain entry. So the trigger on J81 Linux is the state-0 release itself, together with an entry that needs the GPU clock. How Apple's identical store avoids that is still not visible from host code. The cheapest way round it is to skip the state-0 release, since the walk runs at 0→1 anyway. That is boot X1.

## Findings

**Q1, located (code). What `+0x20000` is for** (t1). Every access in the kext:
- **bootFirmware** (fw `+0xc0`, `0x669036c`): slot `0x60 (0)` (store 0, load-back), then slot `0x10 (1)` (poll busy, store `0x11`, one load), then `waitForFWAlive`. GPC state 0.
- **stop/park** (fw `+0xc8`, `0x6690424`): only when Fender is marked powered. Release, then a state-0 request. The GPU is running at this point.
- **META recovery** (`0x6694234`): release, then a state-0 request.
- **hold** (fw `+0xd8`, `0x66906f8`): reached only from the GPU restart path (`0x6675590`, after "%s restart"):
  - store `0x20` and load back;
  - poll bit 5 until it reads 1;
  - poll `+0x1000` bit 4 until clear;
  - then `+0 = 0x40000000`, then the RGX-access check, then the META slave port.

  The routine does not release the hold.
- **Reads:** only the "Pre-inspection fender snapshot" (slot `0x48`, caller `0x66a6608`) and the failure dump.
- **Boot order** (`0x6671f98`–`0x6672014`): fw `+0x228 (1)` power-on, fw `+0xe0` hardware start (stream stored), accel `0x8a8 (1)`, fw `+0xc0`. The hold is not on this path.

Reading (inferred): `+0x20000` is a perf-state override.
- Bit 5 means "override in force". Taking it makes Fender go through a transition (the busy poll after bit 5) and keeps the GPU at a fixed state while the host drives META directly.
- Writing 0 gives control back to `PERF_STATE_CONTROL`, which is why every release is followed at once by a state request.
- The code does not say that the walk depends on the release, and runs 38/39 show it doesn't.

**Q2, located for Apple (code); not separable for h12 (capture)** (t2).
- After the boot release, Apple reads no RGX register. `waitForFWAlive` (`0x6694d40`) sleeps on its alive flag (fw `+0xb35`) through the command gate, with a deadline of accel `+0xc20` seconds, until the interrupt path sets the flag.
- Later direct RGX access is gated by fw `+0x240` (`0x6692828`): with Fender, it is true only if 1 ≤ GPC state ≤ the firmware's maximum and `+0` bit 29 (SNOOP) is clear. Ten call sites use it (t2).
- None of h12's reads (`0x3800`/`0x3804`/`0x3808`/`0xbf8`/`0x20`) has an Apple counterpart right after a release. Apple's state-1 releases are followed by a state-0 request and nothing else.
- The same five reads returned at h11 in runs 33, 35, 38 and 39, after a 0→1 with no release since.

So the h12 hang is most likely either the state-1 release itself, or the reads made while Fender is in a transition after it. Boot X2 separates the two.

**Q3, located (code; capture). The clock:**
- No host write starts an RGX or META clock. Apple never writes `CLK_CTRL` (request 11) and makes no PMGR perf write (request 8).
- PLL5 bit 30 sets after the `0x11` request (runs 11, 33, 38, 39), so the 0→1 transition itself brings up the clock.
- Safe reads: the five h11 reads in state 1 after a 0→1, with no release since (capture). `0x20` is one of them, not the only one.
- Unsafe or unknown:
  - any RGX read in state 0;
  - any RGX read right after a state-1 release (runs 38/39);
  - `0x100` (unresolved since run 38).

**Q4, located (code). Apple's order:**
1. Power-on.
2. Stream stored in state 0 (fw `+0xe0`).
3. accel `0x8a8 (1)`.
4. Release in state 0.
5. State-1 request, then wait for alive.

Apple never requests state 1 before storing or releasing. Its list includes the reset asserts and the SLC pair, the same entries that hang the runner's state-0 release. Together with runs 38/39 (the walk runs at 0→1 without a release), this points to a practical route. Store the full list in state 0, **skip the state-0 release**, and let the 0→1 walk apply it with the clock coming up. This departs from Apple's sequence, and it is inferred to work until X1 runs.

## Q5: next boots (all with h3pb; one change each)

Full table in t3.
1. **X1, resets at 0→1, no release:** run 36's four SOFT_RESET entries plus `META_BOOT 0x0bf8 ← 1` as the last entry; h8n; stop after h11 (no h12).
   - Pass with `h_x[0] = 1`: the walk got through the resets once the clock ran, so the state-0 release is the hang trigger.
   - This is the most informative boot.
2. **X2, release alone in state 1:** empty list, h8n, h9–h11, then h12 with the store and the GPC_STATE poll but **no RGX read**. Record `r5` and the PMGR observers.
   - Pass: runs 38/39 hung on the reads.
   - Hang: the state-1 release hangs by itself.
3. **X3, only if X2 passes:** X2 plus a single `0x20` read after the poll.
4. **X4, only if X1 passes:** X1 with the SLC pair (`0x3800`, `0x3808 ← 1`) before the META_BOOT marker. Expect `0x00300001`/`1` at h11.
5. Your (iv), resets stored in state 0 and released in state 1, mixes the two suspects. X1 and X2 separate them.

Your (i) is X2 without the reads; your (ii) and (iii) are X2 and X3.

Avoid:
- any state-0 release with a non-plain list;
- RGX reads after a state-1 release until X2/X3 clear them;
- `+0x20000` reads before it is written;
- the hold in state 0;
- PMGR `+0x5004` after `+0` and before state 1;
- `0x100` reads;
- BIF entries without a real page catalogue.

## Not resolved

- How Apple's identical state-0 release completes with the reset list on iOS. One host-visible difference remains: Apple's second state-0 request does not wait for completion (request 11, boot AT).
- What each of the ten RGX-access check callers protects. They are listed, not decoded.
- Whether the walk at 0→1 also handles the SLC pair (X4).

## Files

- `t1-override-accesses.tsv`: Q1, every `+0x20000` access, its context and what follows, plus the boot order.
- `t2-rgx-access.tsv`: Q2/Q3, Apple's RGX-access check and its callers, what follows the boot release, the clock, and the reads proven safe.
- `t3-next-boots.tsv`: Q5, the ranked boots with what to read in the status line.
- `SHA256SUMS`.
