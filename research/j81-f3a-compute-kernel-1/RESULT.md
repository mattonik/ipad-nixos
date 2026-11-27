# Research request 33 result: the first compute kernel on J81 (J2)

Sources:
- **Orchard's public A8 iOS capture**, `OrchardLinux/gpu a8/M2-IOS-CAPTURE.md`: Metal compute jobs captured on an A8 under **iPadOS 15**, our OS generation;
- **Orchard's A10 notes and headers** (`a10/ISA.md`, `a10/COMPUTE.md`, `tools/a10/tools/g9p-cdm.h`);
- **Orchard's Mesa** (`src/imagination/g5p/README.md`, `g5p_cdm.h`);
- **Mesa's Rogue `cdm.xml`**.

All of it was read on GitHub. Orchard's G9P encoder (`tools/a10/tools/isa/g9p.py`) was blocked by the proxy and not read. Tags: **orchard**, **source**, **capture**, **inferred**. The words below are the ones published in those public notes.

## Short answer

- **The ISA is Apple's, not Mesa's Rogue USC.** The A8's USC encoding is the A10 (G9P) family: 16-bit words, `0xc000` padding, an `0x8000` end word at a 64-byte boundary. Orchard compiles A8 compute with its G9P compiler in A9 mode (`apple_g4p`). Mesa's `rogue`/`pco` encoder doesn't apply.
- **Everything around the kernel is documented for our generation, and the CDM is plain Rogue** (t1, t2). Orchard's capture on an A8 under iPadOS 15 gives:
  - **seven-word kernel records:** `{0x2106, PDS data offset, PDS code offset, 0, 0, 0, 0x40000000}`, then `0x80000000`;
  - **the empty kernel:** byte-identical to the A10's, `0100 0140 0000`, `c000` × 29, `8000`;
  - **its PDS program and data:** `f4000002 d3000000`, data `{USC offset, 0x10}`;
  - **the store kernel's PDS:** `c2c00002 d3000000 f0024001 fc000002 d3000000`;
  - **the binding DMA:** `f0040000 f4060100 d3000000`, data `{entry VA, entry VA + 8, 0x10000002, 0x90004001}`.
- **Offsets are relative to the PDS exec base and the USC code base,** which are one pipeline heap on iOS. **J1 didn't test this**: its HALT sits in the terminate and context-store PDS slots, which run only on a context store (inferred).
  - Map the pipeline heap at the base the config heap-base words hold, and mirror Metal's layout: USC at `+0x40`, PDS data at `+0x100`, PDS code at `+0x120` (t3).
- **The A8 store kernel's USC bytes aren't published.** It's about `0x50` bytes, where the A10's is `0x38`, so the A10 pieces can't be assumed to give it. Generate it with Orchard's G9P compiler (Mesa, A9 mode with `apple_g4p`), storing `0xcafe0001`.

## Q1: the USC kernel (t1)

- **The empty kernel:** 66 bytes, starting on a 64-byte boundary. Its words come from Orchard's public notes and match the A8 capture.
- **The store kernel:** taken from Orchard's compiler (see above). It needs the argument-table entry `{output VA, 0x00010001}` in the common store, loaded by record 0's DMA.
- **Not needed:** no scratch, and no fence or wait is visible in the frame beyond the epilogue.

## Q2: the PDS programs (t1)

- **Empty kernel:** DOUTU with END, then HALT; data `{USC offset, 0x10}`.
- **Store kernel:** Metal's A8 words above. The A8 DOUT is in Rogue's layout (`g5p_cdm.h`).
- **Descriptors:** the K0 sizes word is `0x2106`: usc_unified 2, pds_temp 1, pds_data 1, usc_target 1. The binding DMA uses `0x40008`.

## Q3: the CDM stream (t2)

- **Field decodes:** t2 decodes every K word against Mesa's `cdm.xml`.
- **For 1 × 1 × 1:** KERNEL3–5 are 0, and KERNEL8 is `0x40000000` (max_instances 8, Apple's value).
- **The kernel's PDS program is named by the CDM record.** The record fields W`+0x68`/`+0x21c`/`+0x22c` stay the HALT, because they are the terminate and context-store programs.

## Q4: placement (t3)

- **Pipeline heap:** at the configured base.
- **CDM stream:** as in J1.
- **Output page:** SLC bypass, or flush `0x3818` before reading.
- **The rest:** the argument table in any mapped page, and J1's zero page, hardware objects and data page kept as they are.

## Q5: completion, failures, bisect (t4)

1. **J2a:** a PDS-only task (the binding DMA, no USC).
2. **J2a′:** the same, aimed at an unmapped VA. A fault at exactly that VA proves the PDS ran.
3. **J2b:** the empty USC kernel.
4. **J2c:** the store kernel.

A bank-0 fault address tells which base is wrong: heap base + code offset means the PDS base, `+0x40` means the USC base. If J2b or J2c stall, add an end-of-pass barrier. Metal's A8 stream has three more records, and on the A10 Orchard found the GPU can wedge without them; their A8 programs aren't published.

## Q6: cross-check

Orchard's A8 capture under iPadOS 15 shows Metal's `store_marker` and `store_marker2` writing `0x1357` and `0x2468` with exactly these records and PDS words. Orchard's A10 test tool runs a hand-built stream with a self-encoded store kernel (`0x1357`). A Linux-side A8 store-kernel run isn't shown in the public notes.

## Not resolved

- The A8 store kernel's USC bytes.
- Which config words hold the PDS and USC bases on J81.
- Whether a single dispatch needs the end-of-pass records on the A8.

## Files

- `t1-payload-words.tsv`: Q1/Q2, the USC kernel, PDS programs, PDS data and argument entry, with byte offsets.
- `t2-cdm-words.tsv`: Q3, every CDM word with its field decode.
- `t3-placement.tsv`: Q4, the address convention and slot 1's layout.
- `t4-boots.tsv`: Q5, the bisect boots with their failure signatures.
- `SHA256SUMS`.
