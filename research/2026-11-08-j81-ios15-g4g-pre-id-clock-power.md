# J81 iOS 15 G4G: clock/power calls before the first GPU ID read

Date: 2026-11-08. Offline static review of the local iPadOS 15.8.8 J81
kernelcache disassembly (`artifacts/live/private/gpu-offline/ios15-agx-disasm.txt`,
function `FUN_fffffff00668322c`, `0x...322c`–`0x...3ecc`). No device, build or
MMIO access.

## Result

iOS 15's G4G probe makes exactly one clock request and one power request
before the RGX identity read, in the same order as iOS 8.1. No other explicit
clock or power calls appear on the G4G path; indirect provider side effects of
those calls are not traced here. The iOS 15 code adds no new pre-ID call that
Linux test4 could have missed.

Instruction order on the path that reaches the identity read:

| Address (`0xfffffff00668…`) | Action | Guard |
|---|---|---|
| `3450`–`3640` | Reads boot-args `gpu` (default 2 if absent), `gpu_acceleration`, and provider properties `model-slow`, `no-gpc`, `has-kf` into globals `0x...7a4d878..882` | none |
| `3644`–`36d8` | Provider `+0x3c0` returns the device-memory count. A jump table at `0xfffffff0057c317d` (`00 0c 03 0f`) picks the memory indices. For count 2: RGX index 0, GPC index 1. Index 1 shifts to RGX only for count 4, or for count 3 with `has-kf` | none |
| `38bc`–`38d4` | Provider `+0x3d0(index 0x87c, 0)` maps the RGX memory into global `0x...7a4d8a0` | `0x882` bit 0 (driver enabled) |
| `38e4`–`38fc` | Same call with index `0x87d` maps the GPC memory into global `0x...7a4d8a8` | bit 0 and bit 2 (GPC in use) |
| `3918`–`3930` | **Provider `+0x568(1, 0)`: clock enable, gate index 0** | `0x...7a4d880 == 0` (first init) and bit 0 |
| `3934`–`394c` | **Provider `+0x570(1, &out, 0)`: power enable, gate index 0**. `out` is pre-zeroed at `390c` | same |
| `3968`–`39a0` | GPC map `+0x78` gives the base. If `has-kf` is clear: `+0x10000 = 0xffff0000`, `+0 = 0x40000000`. Then `+0x1000 = 0x11` and an unbounded poll while bit 4 is set | bit 2 and poll byte `0x87f` |
| `39a4`–`39ac` | 10 µs delay, then sets `0x880 = 1` | — |
| `39c0`–`39e4` | RGX map (global `0x8a0`) `+0x78` gives the virtual base, stored at `this+0xd10`. Vtable `+0xa38` (identity) reads `+0x20`, then `+0x18` | bit 0 |

The two provider slots match iOS 8.1's `+0x560` (clock) and `+0x568` (power),
shifted by one vtable entry in iOS 15. Both the IOService memory slots
(`+0x3c0/+0x3c8/+0x3d0` against 8.1's `+0x3b8/+0x3c0/+0x3c8`) and the
argument shapes support this. The clock call takes 2 args, the power call takes
3 with an output pointer. The probe's own cleanup at `0x...3314`–`333c`
mirrors this order: power `+0x570(0,0,0)` first, then clock `+0x568(0,0)`.
This mapping is inferred from the consistent shift and the call shapes. The
iOS 15 vtable was not dumped by symbol. Neither return value is checked
before the identity read, which matches iOS 8.1
(`2026-11-07-j81-pre-id-provider-return-gate.md`).

J81 `sgx` has two `reg` entries and no `gfx-kf`. So iOS 15 reads identity
through `reg` index 0 (`0x201000000`), and GPC is `reg` index 1
(`0x201e00000`). This is the same as the iOS 8.1 provenance in
`2026-11-07-j81-core-map-provenance.md`.

## Correction to the earlier iOS 15 note

`2026-11-07-j81-ios15-g4g-pre-id-mmio-sites.md` states that `this+0xd10`
comes from a provider `+0x98` lookup with index 7, stored at object field
`+0x8a0` in `FUN_fffffff006687dac`. That is a different `+0x8a0`. In
`FUN_...7dac`, `x19` is a large object (it also writes `+0x168`, `+0x838`,
`+0x898`). At `0x...39c0`, the identity path loads the **global**
`0xfffffff007a4d8a0` (`adrp x8, 0xfffffff007a4d000; ldr x0, [x8, #0x8a0]`).
The probe filled that global at `0x...38d4` from `mapDeviceMemoryWithIndex`
with the RGX index chosen above. So the identity read uses `reg` index 0,
not a provider index 7.

## What this means for the next step

The only explicit pre-ID clock request in iOS 15 is the provider clock enable
for `clock-gates[0]`, the same call already traced on iOS 8.1. On iOS 8.1 it goes
to the PMGR per-device reference count. On a 0→1 edge it requests PMGR state
15, applies selectors 9 and 10, and takes a SoC-busy reference
(`2026-11-07-j81-gfx-clock-reference-startup-audit.md`). The G4G probe itself
offers no further lead. The remaining offline question has moved into the PMGR
provider:

1. Check whether iOS 15's `ApplePMGR`/`AppleT7001PMGR` clock callback does the
   same work as 8.1. That means the same state request, the same selector
   tables, and the same busy accounting, or something extra such as an added
   reset, a clock-mux write or an ordering step. Local inputs:
   `ios15-ApplePMGR.raw`, `ios15-AppleT7001PMGR.raw`.
2. Close the open 8.1 item: whether any other consumer requests gate ID 124
   before G4G probes.

Only a concrete register write that test4 did not perform would justify a
new hardware test. That would also need the safety conditions in
`2026-11-08-j81-next-mcc-experiment-decision.md`.
