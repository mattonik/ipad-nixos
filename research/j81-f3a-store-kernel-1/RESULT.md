# Research request 34 result: the A8 store kernel for J2c (J81)

Sources:
- the Orchard files in this request's context (OrchardLinux/gpu `e03c572`): `tools/a10/tools/isa/g9p.py`, `tools/a10/tools/g9p-cdm.h`, `a10/ISA.md`, `a10/COMPUTE.md`, `a8/M2-IOS-CAPTURE.md`, `a8/n102/SHADERS.md`. They were read as data; I transcribed the `store_kernel` path into my own script rather than running Orchard's.
- Orchard's Mesa fork, read on GitHub: `src/imagination/g9p/g9p_isa.h` (the A8 encoders) and `vulkan/pvr_arch_g5p_compute.c` (the A8 PDS programs and end of pass).

Tags: **orchard**, **captured** (a word Orchard quotes from its A8 capture), **derived** (from Orchard's encoders), **inferred**.

## Short answer

- **The A10 kernel (t1)** is `store_kernel` evaluated by hand:
  - `0x1357`: `1181 8189 4100 acb7 | 01c8 0302 0101 0120 46d1 | 2198 0300 012f 212a 0154 0038 | 0900 010c 0000 | 2312 0180 8000 | 21c8 0302 0184 46d2 | 0100 010e 0000 | c000×4 | 8000`. That's 33 words, `0x38` bytes of code, and the end word at `0x40`.
  - `0xcafe0001`: the move becomes the 32-bit form `0198 0300 0103 0121 cbfe 0154 0038`.

  The `st_1357` frame matches ISA.md: the branch at byte 30 jumps `0xc` bytes to the epilogue at byte 42, as the published listing says.
- **The A10 kernel won't work on the A8.** Orchard found that **the A9/A10 store "completes on the A8 but stores nothing"**. The A8 has its own address-pair store, quoted from its capture as `2510 0504 8100 4020` (`k_store_one`: store r2 to `[r0:r1]`). It also has no buffer-form store, so the kernel builds the address from the common store first.
- **The best-supported A8 kernel for `0xcafe0001` (t2)** is 65 words, `0x82` bytes:
  ```
  1181 8189 4100 acb7 | 01c8 0306 0101 0120 46d1 |
  0198 0300 0181 4100 0154 0038 | 0198 0302 0185 4100 0154 0038 |
  0198 0304 0103 0121 cbfe 0154 0038 | 0900 010e 0000 |
  2510 0504 8100 4020 | 21c8 0306 018c 46d2 | 0100 0132 0000 |
  c000×22 | 8000
  ```
  - **Captured words:** the prologue, the store, the common-store move form, and the padding/end pattern.
  - **Derived words:** the register-stack set-up and epilogue, the immediate move and the branches, all from Orchard's encoders, which have no A8 variant for them.
  - **Consistency with the capture:** `0x54` bytes of code (the capture says "about 0x50") and the end word at `+0x80` (the capture: `+0x1300` → `+0x1380`).
  - **Not settled:** that the binding lands in common dwords 0/1. Orchard's notes say the shader reads its buffer from there, and their A8 address build uses dword 1 for the high word.
- **J2c's stream (t4)** is five pieces:
  1. the binding DMA record (`0x40008`);
  2. the kernel record (`0x2106`, its PDS `c2c00002 d3000000 f0024001 fc000002 d3000000`, data `{USC offset, 0x10, 0x80000000, 0}`);
  3. **the A8 end of pass**, which Orchard found necessary (the A9 tail locks the A8 up): an empty USC task, K0 `0x4`, K1 `| 0xa`, PDS `c2c00002 d3000000 fc000002 d3000000`;
  4. a fenced DOUTC task, K0 `0x7`, K1 `| 0x4`, PDS `c2c00002 d3000000 f0000005 d3000000`, data zero;
  5. the terminate.

## Q1 (t1)

Every word of the A10 kernel is tabulated with its instruction, decode and source, for both values. I checked my transcription by asserting it equals the whole `program()` output.

## Q2 (t2, t3)

**A8 against A10:**
- the prologue is the same for a kernel whose record has no common store;
- the immediate move has no A8 form;
- the store has the A8-only form;
- the address is built from the common store, because the A9's 64-bit add of a uniform pair faults on the A8;
- the frame is the same.

The extra length over the A10 is the two common-store moves (`0x18`) plus the store's fourth word.

**Not derivable here:** Metal's exact A8 kernel bytes, which are private captures, and whether Apple's kernel builds the low address word the same way.

## Q3 (t3)

The binding DMA loads `{output VA (two dwords), 0x00010001}` into the common store. On the A8 the kernel moves common dwords 0 and 1 into `r0`:`r1` and stores through the pair (`store_at`, pair 0). The A10's "buffer 0 at offset 0" form is the one that stores nothing on the A8.

## Q4 (t4, t5)

- **The records:** confirmed as listed above.
- **`0x80000000`:** constant for plain kernels; it doesn't depend on the stored value.
- **The USC kernel** may sit anywhere 64-byte aligned in the single execution heap at `0x3_00000000` (USC offset = VA − `0x3_00000000`).

## Q5 (t4, t5)

A single job needs Orchard's two-record A8 tail. Metal's first trailing record (`40008 1488a 14800`, a DMA plus a USC program) is left out by Orchard; their notes say K0 + K4 alone completes. Metal's other two match Orchard's tail records.

## Q6 (t5)

**The exact public route** is Orchard's Mesa G9P compiler with `g5p_usc_g4p` set. The PDS programs and records come from `pvr_arch_g5p_compute.c`. The kernel driver embeds no compute shader, and Metal's binaries are private.

## Not resolved

- The common-store dword layout of the binding (dwords 0/1 is inferred).
- The derived words above.
- Metal's own A8 store kernel words.

## Files

- `t1-a10-store-kernel.tsv`: Q1, every A10 kernel word for `0x1357` and `0xcafe0001`.
- `t2-a8-store-kernel.tsv`: Q2, every A8 kernel word with its confidence.
- `t3-a8-differences.tsv`: Q2/Q3, A8 against A10, instruction by instruction.
- `t4-j2c-stream.tsv`: Q4/Q5, the five-piece J2c stream with PDS code and data.
- `t5-answers.tsv`: Q4–Q6, the remaining answers.
- `SHA256SUMS`.
