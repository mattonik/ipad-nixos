# J81 iOS 15 T7000 clock-action boundary

Date: 2026-11-08. Offline static trace of the local iPadOS 15.8.8
`AppleT7000` and `ApplePMGR` slices. No device, build, or MMIO access.

## Resolved record actions

In `ios15t7000-special.c`, `FUN_fffffff006c961f8` selects a 0x2c-byte
clock record through the index map at `this+0x310` and record table at
`this+0x850`. The J81 GFX record has ID 124, flags `0x06`, selectors 9/10,
and state index 100. For those flags, bit 1 calls
`FUN_fffffff006c97278`, which copies the selected offset/value pairs using
plain 32-bit stores; bit 2 calls `FUN_fffffff006c9739c`. GFX bit 3 and bit 4
are clear, so this record does not take those special-action branches.

`FUN_fffffff006c9739c` adjusts the busy count at `this+0xa50`. Display/cache
work is gated by `this+0xa80 != 0`, byte `this+0xa8c != 0`, a 0-to-1 or
1-to-0 busy-count edge, and a non-null callback object at `this+0xa90`.
On such an edge it calls `this` vtable `+0x740` with codes
`0x2700c001`/`0x2700c002`, invokes the callback object's vtable `+0x80`,
and on callback success may call `FUN_fffffff006c972cc` and `this` vtable
`+0x678`; it then clears a bit in the object's bitmap. The `+0x740` target
is not resolved by this trace. The codes are identified as kdebug trace
codes in [the PMGR trace-code note](2026-11-08-j81-pmgr-2700c00x-are-trace-codes.md),
but that does not resolve this vtable target.

`FUN_fffffff006c939d8` is a concrete indexed-state helper: it bounds the
index below `0x65`, addresses the mapped PMGR word at `+0x20000 + 8*index`,
and uses `FUN_fffffff006c9716c` for the state operation. The available direct
cross-references do not establish that the G4G provider clock callback
reaches this helper or `FUN_fffffff006c961f8`.

## Open callback link

The iOS 15 G4G probe calls provider `+0x568(1,0)` and then `+0x570(1,&out,0)`
before GPC setup. Their clock/power interpretation is inferred from the
argument shapes and slot shift relative to iOS 8.1; the iOS 15 provider
vtable targets have not been resolved. The callback route is expected to
cross AppleARMIODevice/AppleT7001IO code, whose iOS 15 implementations and
relocated vtable metadata are absent from the extracted workspace. The
available `ApplePMGR`, `AppleT7000`, and `AppleT7001PMGR` slices are not enough
to prove a per-device reference count or the callback-to-state/action path.
No behavior from iOS 8.1 is assumed here.

Relevant companion notes: [iOS 15 G4G pre-ID call trace](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md),
[iOS 15 clock-provider reconstruction](2026-11-06-j81-ios15-clock-provider-reconstruction.md).
