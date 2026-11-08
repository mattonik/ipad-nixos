# J81 iOS 15 G4G pre-identity MMIO sites (bounded static inventory)

Date: 2026-11-08. Offline kernelcache/disassembly review only. No patches or
device access.

## Scope and artifacts

The input is the locally decoded J81 iPadOS 15.8.8 kernelcache and its AGX G4G
Ghidra disassembly/decompilation in `artifacts/live/private/gpu-offline/`
(`ios15-kernel`, `ios15-agx-disasm.txt`, `ios15-g4g-probe.c`). The inspected
function `FUN_fffffff00668322c` starts at `0xfffffff00668322c` in the
disassembly and is decompiled in `ios15-g4g-probe.c`; this inventory covers
only its two GPC sequences and the adjacent direct RGX reads in
`FUN_fffffff00669bb54`. It is not a whole-kernel MMIO census.

## Observed sites, in instruction order

| Instruction address | Access and condition | Static interpretation / limit |
|---|---|---|
| `0xfffffff0066832f8` call through `+0x78`; `...3300` store; `...3304` load; `...3308` test | Obtains a mapped base, writes `0x10` to base `+0x1000`, repeatedly reads the same register while bit 4 is set. Entered only on the existing-global-object path: global pointer non-null; `DAT_...d880 != 0`; config bit 2 set; and flag byte nonzero (`ios15-agx-disasm.txt` `0x...6832c4–3308`). | Conditional prior-state GPC shutdown/poll before the current-object path. The base is returned by the `+0x78` call; mapping identity is not independently resolved here. Poll is unbounded in these instructions. |
| `0xfffffff006683968–3974` | Calls through a mapped-object `+0x78` method to obtain base in `x0`; then loads a flag byte at `...3978`. | Setup path begins only if the outer condition at `...3950–395c` passes: object byte bit 2 set and the second byte nonzero. |
| `0xfffffff006683980`, `...3988` | If flag bit 3 is clear (`tbnz` at `...397c` skips these when set), writes `0xffff0000` to base `+0x10000`, then `0x40000000` to base `+0`. | The first two GPC writes are conditional on the flag. The instructions do not read either address back. |
| `0xfffffff006683994`, `...3998`, `...399c`, `...39a0` | Unconditionally within the outer setup branch, writes `0x11` to base `+0x1000`, reads it, and loops while bit 4 is set. | State transition and busy poll. No timeout is visible in this loop. A 10-us delay call follows at `...39a4–39a8`. |
| `0xfffffff00669bb58`, `...69bb5c` | In `FUN_fffffff00669bb54`, loads a 32-bit value from `[x8 + 0x20]`, then `[x8 + 0x18]`; `x8` was loaded from object field `[x0 + 0xd10]` at `...69bb54`. | Two direct reads through an object-held mapping pointer. The full kernelcache's `__const` table has `FUN_fffffff00669bb54` at `0xfffffff006f2fd18`; subtracting the caller's slot offset `0xa38` gives vtable base `0xfffffff006f2f2e0`. Thus the `+0xa38` dispatch in `FUN_fffffff00668322c` resolves to this exact identity routine for objects using that vtable. |

The accesses above are the only sites claimed here. The reads at
`...69bb58/5c` are the identity-read boundary; the two GPC regions are the
before-boundary setup/cleanup sites in the inspected method. No addresses are
re-labelled as physical addresses from these instructions alone.

## Comparison with prior evidence

- The iOS 8.1 static trace records GPC writes `+0x10000=0xffff0000`,
  `+0=0x40000000`, then `+0x1000=0x11`, a bit-4 poll, a 10-us delay, and the
  identity method reading RGX `+0x20` then `+0x18`; afterward it requests GPC
  state zero. See `research/2026-11-07-j81-gpc-hold-before-id-boundary.md:17-37,92-99`.
  The iOS15 disassembly shows matching offset/value/order patterns in the
  inspected function, with the branch conditions listed above. This is a
  structural comparison, not proof that both OS versions take identical paths
  on J81.
- Linux test4 reached PMGR `0x3ff`, GPC state `1` and control
  `0x40000000`, then the host's first-read checkpoint at
  `0x201000020` did not complete. The capture therefore does not establish
  successful RGX reads or explain the cause. See
  `research/2026-11-07-j81-gpc-hold-before-id-boundary.md:116-123` and
  `research/2026-11-07-j81-core-revision-after-clock-test4.md:5-7`.

## Unknowns and next offline step

The `+0xd10` mapping flow is now resolved to its API-level source. In
`FUN_fffffff006687dac`, the object stores the result of a provider-object
virtual call (`+0x98`) made with index `7` and options `0x80007`. In `FUN_fffffff0066839c0–39d4`, that retained map object's
`+0x78` method supplies the virtual base stored at `this+0xd10`. The identity
method then reads that base at `+0x20` and `+0x18`. This proves the value is a
kernel virtual mapping derived from provider memory index 7; it does not by
itself identify that provider entry's physical range/name. Do not equate index
7 with `sgx` DT `reg` index 7 without tracing the provider descriptor.

The dynamic branch values and whether either unbounded poll terminates on
J81 remain unknown. The test4 hang is not evidence that iOS takes the same
branch or sees the same value.

Next offline verification: trace provider memory index 7 through its descriptor
to a named/physical resource, then resolve the `+0x78` map-return method. Do not
infer further register behavior from offset similarity alone.

## Resolution evidence (2026-11-08)

- The full original `ios15-kernel` Mach-O was loaded in Ghidra with no analysis;
  a read-only memory scan for the 64-bit code pointer `0xfffffff00669bb54`
  found the single `__const` occurrence at `0xfffffff006f2fd18`. The caller
  loads its method pointer from vtable byte offset `0xa38`, so the corresponding
  vtable base is `0xfffffff006f2f2e0`. This directly resolves the dispatch to
  `FUN_fffffff00669bb54` without relying on names inferred from nearby code.
- `ios15-agx-disasm.txt` at `0xfffffff006687d94–7dac` shows a memory lookup
  through the provider object's slot `+0x98`, with the index/flags values `7` and `0x80007`, then stores its result in
  object field `+0x8a0`. At `0xfffffff0066839c0–39d4`, the code calls the
  retained map object's `+0x78` method and stores the returned base at
  `+0xd10`. This is the exact map object consumed by the resolved identity
  routine. The local disassembly proves provider memory index 7, but this
  review did not trace the provider descriptor to a physical address or named
  DT resource.
