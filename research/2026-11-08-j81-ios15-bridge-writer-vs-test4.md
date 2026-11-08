# J81 iOS 15 bridge writer output versus test4

Offline comparison of the saved iOS 15 Ghidra decompilation, raw Pongo ADT
text, and Linux test4 transcript. No device access.

## Writer path and format selection

`bd91a8(pmgr, device_record, state)` walks the device record's bridge count
and selector bytes in order. For each selector it checks that the selected
state table has a non-null settings pointer, then calls `bd4da8(pmgr,
selector, state)`. The device record uses selectors 9 then 10. On this path,
the relevant selection is by `pmgr+0x2680`: format 0 is the legacy
offset/value-pair writer (`bd40bc`); format 2 or higher selects the other
writer (`bd49d0`). Both dispatch each resulting 32-bit register store through
the PMGR register-write virtual at vtable `+0x998`. The alternate format has
separate address synthesis, which has not been resolved here. The saved ADT
has no `bridge-settings-version` property, so its runtime `+0x2680` value
and which writer ran on a particular iOS boot are not established by these
artifacts.

## Missing-property default and limits

The static evidence favors format 0 on the ordinary allocation path. In the
local iOS 15 cache, the `AppleT7001PMGR` allocation path calls
`OSObject_typed_operator_new` at `0xfffffff007689f84`; its normal zone path
passes `0x000d1004` to `zalloc_flags`. `Z_ZERO` is bit `0x0004` in the XNU
8020-series allocator definition, so that allocation is zero-filled. The
shared and J81 subclass constructors in the extracted cache have no direct
store to the format field at `pmgr+0x2680`. The PMGR initializer assigns the
field when `bridge-settings-version` is present; this ADT capture has no such
property. These facts support an initial value of zero and therefore the
legacy writer on this normal path, but do not prove the value at a particular
boot: an intervening initializer, alternate allocation path, or later store
could change it.

Independent exact-offset scan: Ghidra `FindImm` over the shared
`ios15-ApplePMGR.raw` code range `0xfffffff006bb9000..0xfffffff006bedfff`
found one instruction storing through immediate offset `0x2680`:
`0xfffffff006bc0334: str w8,[x28,#0x2680]`, in initializer
`0xfffffff006bbf7a4`. Its surrounding instructions fetch a property and write
the field only when the lookup returns a value. The other exact-offset hits
in that image are reads. The same scalar-operand scan over the inspected
`ios15-AppleT7001PMGR.raw` range `0xfffffff006c88000..0xfffffff006c8af28`
found no `0x2680` operands. This checks encoded immediate references in those
code ranges; it does not exclude a computed address, an indirect write through
a pointer/helper, code outside the scanned ranges, or later runtime mutation.

The writer-selection field is `+0x2680`; the separate `+0x2684` word selects
an alternate table/map mode elsewhere in the bridge loop. Do not conflate the
two. The allocation evidence and field inspection are from the local cache,
whose exact 19H422 source IPSW association is verified by matching the
manifest digest, raw cache, and decoded Mach-O. Its embedded
`DTPlatformBuild=19H402` is platform/toolchain metadata, not
`ProductBuildVersion`, and does not contradict that association. This does not
establish that this exact cache is the target's running binary. See the
[provenance note](2026-11-08-j81-ios15-kernelcache-provenance.md).

The alternate `bd49d0` writer is not equivalent to replaying the 33 raw
offset/value pairs. Its decompilation walks state-specific setting records
(36-byte records), derives register addresses and values from record fields
and indexed PMGR tables, and issues writes through virtual `+0x998`; the
address synthesis has not been fully resolved. The current artifacts do not
establish an exact `bd49d0` address/value sequence for selectors 9 and 10, nor
that this branch ran. Linux test4's 66 checkpoints therefore compare only to
the conditional format-0 output above. They do not exclude writes from other
Apple PMGR paths, an already-active-device path, an initializer or wake path,
or boot firmware; no complete writer audit or hardware register readback was
made here.

For format 0, the decompilation shows a sequence of 32-bit `(offset,value)`
pairs forwarded unchanged to `+0x998`; applying the selector's J81 mapped
base yields the addresses below. The bridge loop emits selector 9's complete
settings before selector 10's. No sorting or deduplication is present in
this path. These address/value results are therefore the legacy-writer
result, conditional on format 0 and the stated selector mappings; they do
not describe `bd49d0` output.

## Exact J81 table result

The GFX device record has two selectors, `[9, 10]`. The Pongo ADT shows both
properties contain the same 264-byte table: 33 pairs. Table pair 0 is
`(0x18, 0x80010004)`; pair 1 is `(0x40000, 0x007c7c01)`; pairs 2 through 32
use offsets `0x40004` through `0x4007c` in four-byte steps. The two selector
tables are byte-identical.

Assuming the legacy writer (format 0), the J81 selector mappings turn table
offsets into these physical addresses:

| Selector | Pair 0 | Pairs 1–32 |
|---|---|---|
| 9 | `0x201f00018` | `0x201f40000`–`0x201f4007c` |
| 10 | `0x201f80018` | `0x201fc0000`–`0x201fc007c` |

The 32 values at offsets `0x40000`–`0x4007c` are identical for selectors 9
and 10, in order:

```
007c7c01 007c7c01 007c7c01 007c7901 007c7901 007c7c01 007c7c01 007c7c01
007c7c01 007c7c01 007c7c01 007c7c01 006c6901 007c7901 007c7c01 007c7c01
00747201 00747201 00747201 00747201 007c7c01 007c7c01 007c7c01 006c6901
007c7c01 00797901 00797901 007c7c01 006c6901 00797901 00797901 00797901
```

## Comparison with Linux test4

`clock-table-20261107-test4.log` records a concrete Linux write sequence
equal to the legacy-writer result above (assuming format 0 and the J81
selector mappings):

1. PMGR power transition had already read back as `0x3ff` (target/actual 15).
2. Selector 9: 33 stores, first `0x201f00018 <- 0x80010004`, then 32 stores
   in ascending order from `0x201f40000` through `0x201f4007c` with the
   values above.
3. Selector 10: the same 33 values in ascending mapped order, beginning
   `0x201f80018 <- 0x80010004` and then `0x201fc0000` through
   `0x201fc007c`.

The transcript has duplicate `stage=` and `host-stage` lines for each
checkpoint; counting unique pair indices gives 33 per selector, 66 total.
Every local after-store checkpoint appears and the helper returns `rc=0`.
Those are progress checkpoints, not reads of all 66 registers. Test4's later
readback confirms `0x201f00018 = 0x80010004`; the remaining table values were
not individually read back. Thus test4's plan matches the static table and
the conditional format-0 mapped address/value/order result. Successful
persistence of all stores is not established.

This does not prove which iOS 15 writer format was active at runtime, and the
modern `bd49d0` output remains unestablished. Nor did Linux invoke Apple's
PMGR callback or ancillary software bookkeeping. The demonstrated equality
is specifically between test4's 66-store plan and the legacy writer's
conditional output for these captured GFX tables.

Sources: `artifacts/live/private/gpu-offline/ios15pmgr-bridge-use.c`,
`ios15t7000-bridge-writer.c`, the Pongo ADT at
`artifacts/live/private/gpu-observations/20261106T060741Z-pongo-adt.adt`,
and `artifacts/live/gpu/clock-table-20261107-test4.log`. Context:
`2026-11-08-j81-ios15-gfx-dependencies-and-bridge-apply.md` and
`2026-11-07-j81-test4-raw-readback-boundary.md`.
