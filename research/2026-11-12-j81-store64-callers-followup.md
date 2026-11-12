# J81 64-bit PMGR store: linkage and caller correction

Offline analysis on 2026-11-12 of the local iPadOS 15.8.5 (19H394)
kernelcache and existing 19H422-associated Ghidra projects. No device
access. This follows and corrects the bounded caller count in the
[64-bit writer note](2026-11-12-j81-page5-64bit-writer-gap.md).

## The indirect pointer is a linkage slot

The 19H394 pointer at `0xfffffff006fe5d40` contains
`0xfffffff006bcf858`, the ordinary 64-bit PMGR writer. The existing
T7001 PMGR disassembly resolves a small linkage thunk at
`0xfffffff006c8ae50` through that slot; it is not established as a
GPU-specific callback or a dynamic vtable entry. The previously documented
19H394/19H422 executable range is byte-identical; the pointer value was
independently read from 19H394's differing data segment.

A four-byte-aligned raw scan of the **19H394 `__PLK_TEXT_EXEC` segment**
for AArch64 immediate `B` and `BL` instructions finds 12 branches to that
thunk, all located within the T7001 PMGR text. Inspection of their local
instructions shows region selector 8; most use fixed small offsets, while
the branch at `c88884` uses `param_2 - 0x220000` after checking
`param_2 & 0xfffff000 == 0x220000`, giving an offset in `0..0xfff`.
Thus these visible calls do not directly request ordinary region 0 offset
`0x5000`. This is a static caller-bound result, not a live trace or proof
that region 8 cannot alias the target.

## The first caller count was incomplete

The same raw scan found 12 immediate branches to `bcf858` in
`__PLK_TEXT_EXEC`, not the four listed by the earlier Ghidra reference
query. Ghidra's auto-analysis merged or failed to decode portions of this
area. The four originally reported sites remain present; the additional
sites at `bcf708`, `bcf770`, `bcf7e4`, `bcf980`, `bcfa34`, `bcfd70`,
`bcfde4` and `bcfe24` are also real instruction encodings. Inspection of
their argument setup finds selectors 8, 8, `0x14`, dynamically selected,
dynamically selected, 9, 9 and `0x15`, respectively. The two dynamic
selector cases use fixed offsets `0x48` and `0x20`. These selector numbers
do not by themselves establish physical addresses or rule out aliases.

The scan treats every aligned word in the specified segment as a candidate
instruction, including possible embedded data; inspect individual call sites
before treating them as reachable code. It covers neither other segments,
indirect call targets nor runtime-generated code. The 12 branches to the
T7001 thunk are separate from the 12 direct branches to the base writer.
Byte identity does not prove that either path ran in the captured boot.

## Decision

The previous concern that a 64-bit store might overlap the watched word is
still technically valid, but these call sites provide **no direct evidence**
that it happens during GPU startup. A new iPad boot solely to test this
coverage gap has low priority. A better next offline question is whether
the PMGR region resolver and live mapping prove region 8/other selectors
cannot alias page 5, or whether a specific caller is reached in the GPC
window. Do not replay a 64-bit store or equate a negative CPU trace with
autonomous hardware activity.

Evidence: 19H394 kernel SHA-256
`c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`;
`ios15t7001pmgr.c` and the local `ios15pmgr`/`ios15t7001pmgr` Ghidra
projects under `artifacts/live/private/gpu-offline/`; local generated
instruction logs `/tmp/j81-store64-extra-force.log` and
`/tmp/j81-t7001-store64-callers.log`. The full prelinked executable hash and
cross-build limits are in [the parity note](2026-11-11-j81-19h394-code-parity.md).
Keep kernel images and private device captures out of Git.
