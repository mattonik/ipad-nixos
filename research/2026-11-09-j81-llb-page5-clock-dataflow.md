# J81 LLB PMGR page 5: bounded clock data flow

Offline analysis of the local decrypted J81 15.8.8 (19H422) and 8.1
(12B410) LLB images on 2026-11-09. No iPad access or MMIO. This extends
[page 5 versus the GFX table](2026-11-09-j81-pmgr-page5-vs-gfx-perf-table.md).
It identifies a software rate calculation involving page 5; it does not
identify the block's electrical function or a GPU dependency.

## Page 5 is read by a rate-calculation loop

In 15.8.8, the setup routine performs the earlier recorded page-5 operations
at `0x1803907d4`–`0x1803907f0`: poll bit 25 of `0x20e005000` until clear,
clear bit 0 at `+4`, and set bit 24 at `+8`. After further setup, instructions
`0x18039095c`–`0x1803909dc` iterate six 4-KiB pages starting at
`0x20e000000`, reading each page's `+0`, `+4`, and conditionally `+8`.
The sixth iteration addresses `0x20e005000`, `0x20e005004`, and
`0x20e005008`. It stores the calculated 32-bit value in element 6 of an
array based at `0x1803b4768`; element 0 is initialized to 24,000,000.
The `+8` read occurs only on the branch where `+0` bit 31 is set.

For each page, the code uses fields in `+0` and `+8` to scale a 24-MHz or
48-MHz base by a 9-bit multiplier and divisors. If `+0` bit 31 is clear,
the computed value is 24 MHz when `+4` bit 0 is set, otherwise zero. This
is strong evidence that the software treats these words as inputs to a
clock-rate calculation. It does not prove that a zero software result means a
physical clock is off. In particular, the meaning of bit 25 in `+0` and bit
24 in `+8`, and the actual values at handoff, remain unknown.

The 8.1 LLB contains the same bounded six-page calculation at
`0x180393188`–`0x18039320c`, including the sixth page and output index 6.
This is an instruction-level comparison, not proof either LLB ran in the
later DFU → PongoOS → Linux boot.

## The inspected selector tables do not directly choose slot 6

In 15.8.8, after calculating the base array, the same startup routine calls
`0x180391770` for six selector records and `0x180391374` for rows 8–54.
Those helpers use a selector read from an MMIO word to index a table of
`(source-array-index, divisor)` pairs, and then use the selected source-array
entry to calculate another value. The six records in rows 55–60 point at
`0x20e010208` through `0x20e01021c`; the first four selectable pairs of
rows 55–58 use source indices 5, 3, 1, and 5. Rows 59–60 use index 5 for
their first four pairs. These are **source-array indices**, not PMGR page
numbers: source index 5 corresponds to the calculation for page 4, while
page 5's calculation is source index 6.

A bounded read of the original 15.8.8 LLB image, treating each of the 53
records in rows 8–60 as a 104-byte record with a pointer and 12 index/divisor
pairs, found **zero source-index-6 entries among 636 pairs**. For example,
rows 55–58 contain `(5,3), (3,1), (1,1), (5,2)`; rows 59–60 contain
`(5,5), (5,7), (5,8), (5,9)` in their first four slots. Those pair values
were read from the private image, not a device. This means the initially
stored pairs in this bounded set do not directly select the page-5 rate.
The code's selector is six bits wide, so selectors beyond the 12 pairs
within a record, runtime table mutation, indirect consumers, other functions,
and hardware-level dependencies are outside this scan. A zero exact-xref
result is not proof of no consumer.

The evidence supports reducing the priority of page 5 as a *direct* GPU
clock selector in this inspected LLB path. It does not prove page 5 is
unrelated to the GPU or that Linux inherited the same configuration as iOS.
The previously identified dedicated GFX perf-slot path remains distinct;
no data-flow link from page 5 to that table was established.

## Evidence and next step

The private decoded 15.8.8 LLB has SHA-256
`493a2a205a7d0fe7161c36d07068c87e93cef70bcc96a1a8519762a8ecf2da46`;
the 8.1 LLB has SHA-256
`2effdec6bc721087364b0d1dbcb41a5c2633b3b1983b5edff005493ad0237c98`.
The load base `0x180380000` for each comes from the respective image's
relocation literal. Private evidence includes `insn_15llb_page5.txt`,
`insn_15llb_page5_consumers.txt`, `insn_81llb_page5_frequency.txt`,
`insn_81llb_frequency_setup.txt`, and `rea-page5-20261109.json` under
`artifacts/live/private/ghidra-iboot/`. REA/Ghidra outputs are static
analysis, not device execution, and omit unresolved indirect edges.

A useful next offline step is to trace the selected GFX perf state and the
provider that can change it, or the boot-chain state observed by a working
iPadOS driver. Neither a page-5 write nor a repeat of the stalled GPU read
follows from this calculation alone.
