# Research request 13 result: the override "hang" is a runner mapping bug; Apple's path from the walk to firmware alive (J81, 19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–12 (sha256 `c3507666…a0008`, AGXG4G), the captured ADT, and the runner source in `context/`.

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **adt**: the captured J81 ADT;
- **capture**: the run log or the runner source;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics and field names.

## The main finding: the runner never writes the override register

`j81-gpu.c` maps the Fender window with `ioremap_np(GPC_BASE 0x201e00000, GPC_SIZE 0x11000)` (lines 45–46, 1351). That covers `0x201e00000`–`0x201e10fff`.

**Every** override access goes through `gpc_regs + 0x20000`, which is `0xf000` past the end of that mapping:
- h8 (line 918);
- h12 and h12s (line 961);
- the merged h6md (line 746);
- step_at (line 713);
- the F steps (`gw`, line 539);
- run 25's read (line 821).

These accesses never reach Fender. They go to whatever kernel virtual address follows the 17-page mapping (capture, certain).

Apple maps the whole window: ADT `sgx` reg[1] is `0x201e00000`, size `0x100000` (adt). The probe maps it with `mapDeviceMemoryWithIndex(index, 0)` (`0x66838c8`–`0x66838f8`, code).

What a stray access does (inferred, from Linux arm64 ioremap/vmalloc behaviour):
- **An unmapped address** (a guard page or a hole): a kernel data abort in the sysfs write. You get no after-line, and the watchdog resets the iPad. That looks exactly like a bus hang.
- **A mapped address** (another ioremap, a vmalloc page, a vmapped kernel stack): the zero lands there, either silently or corrupting something.

This fits the record (t1):
- Since the bridge fix, **every** hang happened at a `gpc_regs + 0x20000` access: runs 31, 32, 34, 36, 37 (h8), 38, 39 (h12) and 43 (h12s).
- **Every** sequence without one completed: runs 40–42 in full, and 38/39 up to h11.
- The three stores that "passed" (runs 30, 33, 35) must have hit a mapped address. Why those three happened to be the plain-list runs is not explained: three of nine boots.

Knock-on effects (capture):
- Run 25's "reading the override hangs" is the same bug.
- The "PMGR `+0x5004` read after `+0` hangs" conclusion (runs 20–23) is unproven too. Each of those runs ended at the h8 step that contained the stray store.
- The walk results (runs 40–42) are unaffected, because ConfigRAM `+0x10000`–`+0x10078` and `+0`/`+0x10`/`+0x1000` are inside the mapping. So are all state requests.

**Fix:** set `GPC_SIZE` to at least `0x21000`, or ioremap the override page `0x201e20000` separately. Then retest the release. Every earlier conclusion about the override itself (requests 6–12 and the run notes) is void until then.

## Findings

**Q1 (code; capture; inferred).** Apart from the mapping, the access is the same as Apple's:
- Apple's release is a 32-bit `str` with no barrier, followed at once by a load-back (`0x669c24c`–`0x669c268`). It goes through a Device mapping created with option 0, the default cache mode, which xnu maps uncached nGnRnE (inferred from xnu).
- The runner's is a 32-bit `writel` to an nGnRnE mapping, followed by a GPC_STATE read.
- Apple's release comes microseconds after `+0 = 0x40000000` with a load-back (`0x6690be4`) and the stream stores. Nothing else touches Fender in between: only the end marker, a timestamp, accel `0x8a8 (1)` and a global read.

So width, ordering, barriers and cache attributes don't explain anything. No clock-domain theory is needed until the release has actually reached the register once. Even then, every release in Apple's code is followed by a state request (request 12), and Apple never reads RGX after one.

**Q2, located (code). Apple's sequence from power-on to firmware alive** (t2, with physical addresses and code addresses):
1. GFX PS on, then bridges 9/10.
2. The Fender object is marked powered.
3. `+0x10 = 0`, twice.
4. `+0 = 0x40000000`.
5. The ConfigRAM stream: SOFT_RESET ×3, `META_BOOT ← 1`, `BIF_CAT_BASE0 ← page catalogue`, SLC pair, `SOFT_RESET ← 0`; then the end marker.
6. accel `0x8a8 (1)`: GPU interrupt indices 0/1/4 (AIC `0x86`/`0x87`/`0x8a`) plus the timer and software event sources.
7. The override release.
8. `0x11`, with a pre-poll on the busy bit.
9. The walk at 0→1. META leaves reset at the last SOFT_RESET entry.
10. META boots from GPU VA `0xe1c0000000`: seg2 at offset 0, the boot list at `+0x200` and the tail at `+0xff8` (request 4).
11. The firmware posts a type-0 event record and raises AIC software IRQ 138. Handler `0x6693ea8` stores the record's word `+4` (the META idle PC) at fw `+0xb38`, sets fw `+0x1c8` and `+0xb35`, and wakes the gate.
12. `waitForFWAlive` (`0x6694d40`) has been sleeping on `+0xb35` with a deadline of accel `+0xc20` seconds. It returns without any RGX read, and bootFirmware logs success and sets `+0xb37`.

None of these steps runs with the override held.

The same handler treats type-6 records as the META reset/recovery request (`0x6693efc`). That is where the `+0` value from firmware shared memory and a further release come from.

**Q3 (code).**
- With Fender (the J81 default), bootFirmware **always** releases before `0x11` (`0x669036c`). The hold is taken only in the restart path (fw `+0xd8`, reached from `0x6675590`).
- The only path that skips both is `gpu_gpc=0` (boot-arg read at `0x66834a8`; `0x7a4d882` bit 1 clear). That is the direct path, with no Fender at all: SOFT_RESET is released directly at `0x669034c`.
- Whether the boot release is a no-op cannot be decided from code, because Apple never reads the override first. Now that the runner's "release hangs" results are void, the question is open again. B1 below answers it.
- Omitting it is possible: runs 40–42 show the walk does not need it. Whether firmware DVFM needs it later is unknown.

**Q4, located (code).** `0x3808` appears exactly once in the kext: the stream entry at `0x6699294`, right after `0x3800`. Nothing reads it. That fits a write-only command or self-clearing bit, like upstream's `SLC_CTRL_FLUSH_INVAL` (inferred). Apple's stream does not rely on its later value. Run 41's `0x3808 = 0` is therefore not evidence against the walk.

## Q5: next boots

Full table in t3.
- **B0, read-only, no GPU step:** load the current module and read `/proc/vmallocinfo`. The ioremap line for phys `0x201e00000` gives `gpc_regs`; then see what covers `gpc_regs + 0x20000`. This confirms the explanation without touching hardware.
- **B1, fixed mapping, Apple's own order:** run 36's list plus a META_BOOT marker, a real `+0x20000 = 0` in state 0, then h9–h11.
  - Pass with `0xbf8 = 1`: Apple's sequence works on Linux.
  - Hang: the real release in state 0 does matter. Then use h8n from here on.
- **B2, fixed mapping:** X2 again (a state-1 release with no RGX reads). Apple does this only in stop/park, so it is lower priority than B1.
- **F3a, first firmware run:**
  1. Stage request 4's M0–M3 (the tool's buffer at GPU VA `0xe1c0000000`, a 4 KiB page table, the FWIF blocks and rings, the window table).
  2. Store the full stock list with `BIF_CAT_BASE0` set to the real page-catalogue physical address.
  3. `+0x10 = 0`, `+0 = 0x40000000`, end marker.
  4. Release only if B1 passed; otherwise h8n.
  5. Request `0x11`.
  6. Poll the event-ring write index **in memory** for up to 10 s.

  No RGX read beyond the h11 set, and no META slave-port access before alive.

Avoid:
- any `+0x20000` access with the old mapping;
- reading `+0x20000`;
- META slave-port reads before alive;
- `0x100` reads;
- PMGR `+0x5004` before state 1 (untested, not proven unsafe);
- BIF entries without a real page catalogue.

## Not resolved

- What the stray accesses hit on each boot (B0 shows it for one boot).
- Whether the real override release is harmless in state 0 (B1) and in state 1 (B2).
- Window-table entries 4–9 and the other open FWIF fields from request 4.

## Files

- `t1-mapping-bug.tsv`: every runner `+0x20000` access against Apple's mapping, plus the consequences and the correlation.
- `t2-boot-sequence.tsv`: Q2, Apple's sequence from power-on to alive, with physical addresses, widths, waits and code addresses.
- `t3-next-boots.tsv`: Q5, B0, B1, B2 and F3a, with what to avoid.
- `SHA256SUMS`.
