# Research request 35 result: why J2c completes without storing (J81)

Sources:
- the Orchard files in this request's context (`e03c572`);
- Orchard's Mesa fork (`g9p/g9p_isa.h`, `vulkan/pvr_arch_g5p_compute.c`) and Mesa's `pvr_rogue_pds_defs.h`, read on GitHub;
- the upstream Rogue register headers;
- runs 91–98.

Tags: **orchard**, **source**, **captured**, **derived**, **inferred**.

## Short answer

**The likeliest cause is that the kernel's only lane is disabled, so it stores nothing and faults on nothing** (t1):
- **The lane check:** the kernel's prologue `1181 8189 4100 acb7` compares r0, the local ID, with common-store dword 2 (both halves = threads per group, `0x00010001`), and disables lanes past it (Orchard `g9p_isa.h`).
- **Who fills dword 2:** the binding DMA's second DOUTD. Its control word `0x90004001` means LAST, common store, offset 2, 1 dword.
- **Where that control word is read from:** the A8 DOUT names its control word's data dword in bits 16–23. Metal's code `f0040000 f4060100` reads dwords **4 and 6**, so Metal's data is four 64-bit slots: `{src0, src1, 0x10000002 @4, 0x90004001 @6}`. The A10's `f0001000 f4001808` decode the same way.
- **Orchard's equivalent** packs the control words at dwords 4 and 5 and encodes `f4050100` to match.
- **J2c's suspected mix:** Metal's `f4060100` with `0x90004001` at dword 5. Then the second DMA reads dword 6 = 0, dword 2 stays empty, and the lane is off.

That matches all three runs: stamps 1, output unchanged, and no fault even with an unmapped output (run 98). **Fix one side:** put `0x90004001` at data dword 6 (dword 5 = 0), or change code word 2 to `0xf4050100`.

Everything else in J2c matches Metal and Orchard's A8 plain launch:
- K0 `0x2106` (no fence);
- record 0's `usc_common_shared`, which per `cdm.xml` allocates shared registers that the next kernel reads;
- the DOUTW control `0x80000000`, which writes the local ID into r0;
- DOUTU with CC behind the IF1 branch;
- the two-record A8 tail.

## Q1: fault registers (t2)

- **Main BIF requesters:** bank 0 `0x12b0`/`0x12b8`.
- **META:** bank 1 `0x12c0`/`0x12c8`.
- **Texture and image paths:** TEXAS `0x1430`/`0x1438`.
- **Other status:** BIF_MMU_STATUS `0x12d0`, BIF_FAULT_READ `0x13e0`, EVENT_STATUS `0x130`.

Read all of them in one boot. A disabled lane issues no request, so run 98's silence is the expected outcome.

## Q2: conditions for the store (t1)

The lane check is the condition that isn't met. The common store written by record 0 does persist into record 1: they are shared registers, `usc_common_shared`.

## Q3: common-store layout (t1)

- **DOUTD 1:** `0x10000002` puts the output VA in dwords 0–1.
- **DOUTD 2:** `0x90004001` puts `0x00010001` in dword 2.
- **The kernel's moves:** `0181`/`0185` select common dwords 0/1 (bits 2–6 = dword index, `0x0181 | dword << 2`).

## Q4: kernels that prove execution (t3a, t3b)

- **(a) Loop:** `0100 0100 0000`, `c000`×29, `8000`. It's the proven empty kernel with jump distance 0, so the job should never finish if our USC code runs.
- **(b) Fixed-address store:** r0:r1 = `0x00203000`:0 from immediates, r2 = `0xcafe0001`, the A8 store. 65 words, listed in t3b. It still needs common dword 2, because the prologue checks it.
- **(c) The A9-form store:** we already know from Orchard that it stores nothing on the A8, so it adds no information.

## Q5/Q6: cache and flags (t5)

The fenced DOUTC tail plus the SLC flush is what Orchard relies on. No other cache needs flushing on the A8. valid | bit 3 output pages aren't a known blocker.

## Next boots (t4)

1. **J2c-fix:** the control-word index.
2. **J2L:** the loop kernel.
3. **J2F:** the fixed-address store.
4. **The fault census:** all five banks read together after any J2c.

## Not resolved

- Whether J2c's data block really has `0x90004001` at dword 5. The request's description doesn't show dword positions; please check the module.
- The USC requester tag IDs.

## Files

- `t1-why-no-store.tsv`: Q2/Q3, the lane check, the DMA decode and the likely bug.
- `t2-fault-registers.tsv`: Q1, every register that could latch a failed USC write.
- `t3a-loop-kernel.tsv`: Q4(a), the loop kernel words.
- `t3b-fixed-store-kernel.tsv`: Q4(b), the fixed-address store kernel words.
- `t4-next-boots.tsv`: the ranked boots.
- `t5-cache-pte.tsv`: Q5/Q6, the cache path and page flags.
- `SHA256SUMS`.
