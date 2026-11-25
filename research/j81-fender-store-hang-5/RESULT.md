# Research request 10 result: a no-op entry passes, `0x3808 ← 1` hangs (J81, 19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–9 (sha256 `c3507666…a0008`, AGXG4G kext). I also used earlier results of mine:
- request 4: ConfigRAM protocol and stock list;
- request 6: start-to-stream order;
- request 7: Fender registers.

Register and field names come from upstream Linux `drivers/gpu/drm/imagination/` (`pvr_rogue_cr_defs.h`, `pvr_fw_startstop.c`; kernel.org, current master). That driver targets other Rogue cores, so using its names here is inferred.

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **source**: upstream PowerVR source;
- **capture**: the run log or the runner source in `context/`;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics and field names.

## Findings

**Q1, located (code). Apple never writes `0x3808` alone. It always writes `SLC_CTRL_MISC` first, on a freshly reset SLC.** t1 has the details.
- **The pair:** accelerator vtable `+0x748` = `0x669924c` emits exactly two 64-bit ConfigRAM entries, unconditionally and in this order:
  - `0x3800 ← 0x00035500_00300001`;
  - `0x3808 ← 0x00000000_00000001`.

  Nothing else in the kext names `0x3808`. It is not in the upstream Rogue headers either, so its meaning is unknown.
- **What the first write changes:**
  - On J81, the low word `0x00300001` sets `SLC_CTRL_MISC.ADDR_DECODE_MODE` (bits 23:16) to `0x30` and keeps `BYPASS_BURST_COMBINER` (bit 0). The high word `0x00035500` is the scramble field.
  - After a GFX power-on the runner reads `0x00320001`/`0x00035500` (run 30), so the hardware sits in decode mode **`0x32`**. Apple switches it to `0x30` immediately before it sets `0x3808 = 1`.
  - Run 31 wrote `0x3808 ← 1` without that switch.
- **SLC reset framing:** Apple's list puts the pair after the three SOFT_RESET words, and those reset the SLC first.
  - `SOFT_RESET_SLC_EN` is bit 27 (source).
  - The first two values (`0x00e7fffffffffc1d`, `0x00e7fe071ffffc1d`) have bit 27 set. The third (`0x1_00000000`, `GARTEN_EN` only) clears it.
  - This is the same recipe as upstream `rogue_slc_init()`: everything except the firmware processor is released, then `SLC_CTRL_MISC` is programmed (source). So on Apple's path `0x3808 = 1` lands on an SLC that has just come out of reset with its decode mode reprogrammed.
- **No host-side SLC precondition in the kext (code, by search):**
  - With the J81 GPC bit set, the fw write primitives `+0x1e0`/`+0x1e8`/`+0x1f0` only append ConfigRAM entries. Apple never stores to `0x3800`/`0x3808` directly.
  - The only other SLC accesses are the stop-path idle poll on `SLC_IDLE 0x3898` (`0x66992ac`) and a dump read of `SLC_CTRL_BYPASS 0x3828` (`0x669a258`).
  - The AGX kext has no MCC/AMCC string or access. PMGR's `function-mcc_ctrl` (`0x6bb97a4`) belongs to the memory controller, not the GPU path.

  So what `0x3808 = 1` needs is inside the GPU: the SLC state Apple's own list establishes. It is not a host clock, a PMGR bank or a bridge beyond the bridges 9/10 you now re-apply (inferred).

**Q2, partly located. Host code cannot see the walk; a changing write can** (t2).
- Apple never verifies the walk. After `+0x20000 = 0`, slot `0x60` loads `+0x20000` back once (`0x669c24c`–`0x669c268`). Then `0x11` is requested with a busy poll on `+0x1000` bit 4, and Apple waits for firmware alive.
- No Fender register reports walk progress. The dump names seven registers (request 7), and none is a cursor, status or completion field. ConfigRAM is never read after the store.
- So whether the walk skips same-value entries cannot be decided offline. The store returning (it is non-posted) means Fender accepted it (inferred).
- The only proof is to write a value that **changes** a register you can read in state 1, then read it at h11. Experiment A below does that with Apple's own first SLC write.

Reads after the store:
- Safe:
  - one `+0x20000` load-back right after the store returns (Apple does this);
  - the `+0x1000` busy poll (h9 already does this);
  - RGX `0x3800`/`0x3804`/`0x3808` in state 1 (runs 11 and 30).
- `+0x14` and `+0x8` are interrupt and kick bookkeeping. They are plausible to read in state 1 but say nothing about the walk.
- `+0x1004` is undecoded.

**Q3, located (code; source). Order matters at least for the SLC.**
- Apple's list order: SOFT_RESET ×3, `META_BOOT ← 1`, `BIF_CAT_BASE0 ← page catalogue`, SLC pair, `SOFT_RESET ← 0` (request 4). The `0x1200` value is a real page-catalogue address. The 0 in `fender-configram.tsv` is the tool's placeholder, so never include a BIF entry without a real catalogue.
- **`0x3800` is reachable with SOFT_RESET released.**
  - The runner reads it in state 1 with SOFT_RESET = 0. `step_w2a` requires SOFT_RESET to read 0, and it did (capture).
  - Upstream programs `SLC_CTRL_MISC` with everything except `GARTEN` released (source).
- What is not reproduced is the **SLC reset followed by the decode-mode write** before `0x3808 = 1`.
- META_BOOT and BIF are not needed for SLC register access in the upstream recipe. Whether `0x3808 = 1` needs them is open.

**Leading reading (inferred, moderate).** `0x3808 = 1` switches the SLC into a mode that only works with the SLC configured as Apple configures it (decode mode `0x30`, probably fresh from reset). Written against the power-on configuration, the SLC-side write never completes, so the walk stalls and the non-posted override store hangs. A no-op write of 0 changes nothing, so it either completes or is skipped; run 30 cannot tell which.

## Q4: next experiments (all with h3pb and run 30's order; one ConfigRAM change per boot)

Full table in t3. Ranked:
1. **Boot A, `SLC_CTRL_MISC` alone:** `0x3800 ← 0x00035500_00300001`, Apple's 64-bit entry. The only real change is decode mode `0x32 → 0x30`.
   - Pass and h11 reads `0x3800 = 0x00300001`: the walk executes changing writes, which settles run 30's question and confirms Apple's precondition write is accepted.
   - Hang: no changing SLC write completes; go to D.
   - This is the safest informative write, because Apple makes it on every boot to an idle GPU.
2. **Boot B, if A passes: Apple's SLC pair**, `0x3800` then `0x3808 ← 1` (both 64-bit, as `0x669924c` emits them).
   - Expect `0x3800 = 0x00300001` and `0x3808 = 1` in state 1.
3. **Boot C, if B hangs:** SOFT_RESET ×3 (Apple's values), the SLC pair, then `SOFT_RESET ← 0`. That gives a freshly reset SLC. Run 19 tried this framing around a no-op before the bridge fix, so it never tested this. Leave out META_BOOT and BIF.
4. **Boot D, only if A hangs: `META_BOOT 0x0bf8 ← 1` alone** (your (i)). This is a changing write outside the SLC.
   - Pass with `0xbf8 = 1`: the SLC is the obstacle.
   - Hang: the walk cannot complete any changing write.

   Leaving it at 1 is a mode latch for the next META reset. Nothing persists across a reboot (inferred).
5. Your (ii), SOFT_RESET then `0x3808 ← 1` without `0x3800`, changes two things relative to Apple. Prefer C.

Optional side test to re-explain runs 12–19: run their order with the 66 bridge stores re-applied after h2 (state 0) and no power cycle, using the h7d list.
- A pass would mean the bridges lose their settings at the 1→0 transition itself.
- A hang would mean the PMGR off/on matters.

Reads to avoid in all of these:
- RGX in state 0;
- `+0x20000` before it is written;
- PMGR `+0x5004` after `+0` is written and before state 1;
- extra Fender reads between `+0` and the store;
- any BIF entry without a real page catalogue.

## Not resolved

- What `0x3808` is, and what its bit 0 switches on. It has no name in the kext or upstream.
- Whether the walk skips same-value entries. Boot A answers this.
- Whether `0x3808 = 1` needs the SLC reset (C), META_BOOT or BIF, or only the decode mode (B).
- Why runs 12–19 needed a bridge re-apply when they had no power-off. The side test above addresses this.

## Files

- `t1-slc-path.tsv`: Q1/Q3, every SLC-related access in the AGX kext and the stream order around the SLC pair.
- `t2-walk-observability.tsv`: Q2, what each Fender or RGX read after the store can tell, and whether it is safe.
- `t3-next-boots.tsv`: Q4, the ranked boots with expectations and risk.
- `SHA256SUMS`.
