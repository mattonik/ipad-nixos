# J81 page-5 attribution: an unwatched 64-bit store

Offline investigation of the local 19H422-associated ApplePMGR Ghidra
project and the 19H394 kernel image on 2026-11-12. No device or MMIO access.
The examined prelinked executable range is byte-identical across these builds;
runtime binding, reachability and data are not established by that comparison.

The [last attribution probe](2026-11-12-j81-page5-store-attribution-result.md)
hooks the ordinary and bridge **32-bit** store instructions, comparing the
store's effective virtual address to the address captured by the page-5
32-bit reader. It therefore cannot detect a wider store overlapping that word.

## Concrete alternate instruction

The ApplePMGR routine at `0xfffffff006bcf858` takes an ordinary-region
selector, offset, 64-bit value and instance. It calls the same mapping
resolver `0xfffffff006bc75e4` as the watched 32-bit path, then executes
`str x21,[x8,w19,uxtw]` at `0xfffffff006bcf8a0`. The 24-byte 19H394
instruction sequence at `bcf88c`–`bcf8a0` is unique in the local full
kernel image:

```text
aa1703e0 aa1603e1 aa1403e2 97ffdf53 f9400c08 f8334915
```

The fourth instruction is PC-relative and must be validated in place, not
copied blindly. At the final instruction, `x8 + zero_extend(w19)` is the
effective address and `x21` is the requested 64-bit value. A store beginning
at the captured page-5 `+0` address would overlap all of `+4`; in
little-endian form its upper 32 bits would cover that word. This is a
**candidate coverage gap**, not evidence such a store executed, was
accepted, or caused the observed bit transition. Misaligned accesses and
other overlapping widths require separate architecture and mapping review.

## Callers constrain the hypothesis

**Correction:** a later raw instruction scan found additional direct branches
that Ghidra's incomplete function boundaries missed. See the
[follow-up](2026-11-12-j81-store64-callers-followup.md) before using this
count to decide on a hardware test.

Ghidra reports four direct call/tail-branch sites within the extracted
ApplePMGR image: `bce27c` passes region `0x33`, `bd3300` passes region `8`,
`bcf60c` passes region `8`, and `be453c` passes region `7`. These constant
selectors are visible at the call sites; their actual mapping, index values,
runtime reachability and aliasing remain unverified. They do **not** show a
direct region-0 call at offset `0x5000`. The local 19H394 image also contains
one raw pointer equal to `bcf858` at virtual address `0xfffffff006fe5d40`;
its owner and whether it is used as a runtime dispatch entry are unresolved.
The bounded Ghidra reference search omits unresolved indirect callers and
does not prove there are no other call paths or physical aliases.

## Next discriminator

Resolve the owner and use of the `bcf858` pointer, and trace or instrument
the four callers before deciding whether another boot is worthwhile. A future
guarded store-site hook would need to detect **range overlap**, not just
equal start addresses; record width, full value, context and completion;
exercise a distinct metadata-only positive control; and report in-flight,
overflow, alias and phase-boundary limitations. A no-match still would not
rule out different store sites, mappings, firmware, or autonomous hardware.
Do not infer that a 64-bit write is safe or replay one merely because this
candidate exists. The iOS physical address cross-reference and the captured
object's lifetime remain inferred.

Private evidence: `/tmp/j81-bcf7.log`, `/tmp/j81-store64-refs.log`,
`/tmp/j81-store64-callers.log`, the local `ios15pmgr` Ghidra project and
`artifacts/live/private/gpu-offline/ios1585-19H394-kernel`. Temporary logs
may be deleted independently; they are not the only source of the recorded
instruction bytes. Do not publish private kernel images or full device logs.
