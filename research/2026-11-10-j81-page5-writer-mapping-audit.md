# J81 iOS page-5 writer mapping audit

Offline review of the local 19H394 kernel and captured Pongo ADT; no device
access. This corrects the suggested two-method filter in the earlier
[writer lead](2026-11-10-j81-page5-change-ios-writer-lead.md).

## Two selectors with different meanings

The candidate AppleT7001PMGR instance vtable has `+0x988 -> bd04f0` and
`+0x998 -> bd3d38` in the inspected 19H394 image. These are distinct mapping
families even though their five argument positions have similar shapes:

| Register | `bd04f0` / `+0x988` | `bd3d38` / `+0x998` |
| --- | --- | --- |
| `x0` | PMGR object | PMGR object |
| `w1` | ordinary PMGR region selector | bridge selector |
| `w2` | byte offset in ordinary region | byte offset in bridge mapping |
| `w3` | 32-bit value | 32-bit value |
| `w4` | instance | instance |

At `bd04f0`, `bd0258` checks the region length and `bc75e4` resolves a
per-region/per-instance object; `bd0534` loads its mapping and `bd0538`
stores the requested value. At `bd3d38`, the method indexes a separate
`pmgr+0x2668` bridge table and stores through that bridge's mapped base at
`bd3d4c`. The latter direct function has no visible bounds check. These facts
are from instruction inspection, not runtime object identification.

The instrumented page-5 read used ordinary region `0`, offset `0x5004`,
instance `0`. A matching `+0x988` write with those arguments and the same
PMGR object is therefore a relevant software-write candidate. It remains an
entry request until the store actually executes; `x0` identity can be
compared internally without publishing the pointer.

**The same numeric filter is wrong for `+0x998`.** The captured Pongo ADT has
`bridge-reg-index=2`: bridge selector `0` uses PMGR `reg[2]`, child base
`0x08000000`, size `0x32000`, whereas the ordinary PMGR aperture `reg[0]` is
child base `0x0e000000`, size `0x40000`. The inspected arm-io translation
maps child 0 to `0x200000000`; thus in the captured tree, in-range bridge 0
plus `0x5004` is `0x208005004`, not `0x20e005004`. The difference from
bridge 0 to the page-5 child address `0x0e005004` is `0x06005004`, well
outside its `0x32000` span. A comparison of all 13 captured bridge spans
(`reg[2]` through `reg[14]`) finds none containing that page-5 child address.
This does not rule out malformed/out-of-range offsets, alternate mappings,
aliases, different runtime trees, or direct stores outside these methods.
The ADT mapping is a cross-reference, not proof of the live iOS virtual or
physical mappings.

## Consequences for the next trace

A focused passive trace should first instrument the known `+0x988` path,
filter ordinary region 0, offset `0x5004`, instance 0 and compare the object
with the one used for the working page-5 reads. Capture all threads within a
properly synchronized `C`-to-`M` window. Include a positive-control counter,
explicit window markers, capacity/overflow, and a clear distinction between
request and completed store. Entry-only tracing cannot prove the write
completed. A no-match result excludes only the traced path/filter/window;
other PMGR objects, regions, direct MMIO, bridge aliases, firmware, autonomous
hardware, and read effects remain possible.

`bd04f0` has a nonunique 24-byte prologue (49 matches in the local 19H394
kernel); a 44-byte prefix is unique there. A unique byte pattern alone is
not enough to prove safe hook placement. The `bd3d38` 24-byte prefix is
unique, but any independent bridge-writer trace must translate its actual
mapping or compare its effective address internally—not reuse region 0's
`0x5004` filter. Never print device pointers in shared logs.

Evidence: 19H394 and 19H422-associated kernel images; private instruction
output `artifacts/live/private/gpu-offline/j81-page5-writer-audit/`; Pongo ADT
`artifacts/live/private/gpu-observations/20261106T060741Z-pongo-adt.adt`;
[bridge address reconstruction](2026-11-08-j81-ios15-bridge-writer-vs-test4.md).
No hook was built, no register accessed, and no data was sent to the iPad.

A [store-site design](2026-11-10-j81-page5-writer-hook-design.md) narrows the hook location and describes the concurrency and phase-boundary limits.
