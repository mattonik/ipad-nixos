# J81 PMGR control-bank writes: the remaining concrete provider-window delta

This offline review follows the successful 19H394 provider-window captures.
It uses only the retained captures and local kernelcache disassembly; no iPad
or MMIO access was performed.

## What is now bounded

The two iOS provider callbacks immediately before GPC setup have been covered
at the ordinary ApplePMGR write entry point:

| PMGR virtual method | Resolved 19H394 implementation | Result |
| --- | --- | --- |
| `+0x980` | `0xfffffff006bd0478` | mapped 32-bit read |
| `+0x988` | `0xfffffff006bd04f0` | mapped 32-bit write; captured in the G4G window |
| `+0x990` | `0xfffffff006bd0564` | bounded read/poll only |
| `+0x998` | `0xfffffff006bd3d38` | bridge writer; its selector-9/10 requests were already captured and replayed |

The direct-write capture observed 49 completed `+0x988` calls across the
clock and power callback window.  It did **not** observe the J81 GFX
state-table word at PMGR region-0 `+0x20320`.  The `+0x990` implementation
repeatedly calls `+0x980` and compares masked values; it contains no write.
Therefore a further probe of that poll implementation cannot reveal an
unreplayed PMGR store.

The previously unresolved `bcc56c` post-transition helper is also not a
missing writer.  Its gated selector-1 action (`bd6328`) reads PMGR energy
counter words, and its result is used for per-record timing accounting.  That
path is not a source-backed candidate for enabling RGX CPU register access.

## The concrete remaining delta

The 49 captured writes are not all GFX state requests.  The captured
control-bank subset lands principally in PMGR region-0 `+0x22000` through
`+0x22180`; the remaining writes are state-table slots below GFX index 100.
The first
two callback-window writes, `+0x1008 = 0x40480348` and
`+0x4008 = 0x48480348`, are PMGR addresses.  Their numerical resemblance to
GPU-window offsets is not evidence that they write GPC/page-5 bit 30.

`AppleT7001PMGR::FUN_fffffff006c8a01c` has the same control-bank inclusion
pattern: it walks `0x22000` to `0x22180` in 16-byte steps, skips
`0x22030..0x22070` and `0x22120`, and conditionally sets bit 31.  This matches
the captured address pattern.  It has no GFX state-index argument and does
not access `+0x20320`; it appears to be a board/platform control-bank setup
operation rather than the GFX PMGR state transition itself.

That still leaves a real difference from the raw Linux/Pongo sequence:
Linux replayed GFX state 15 and the 66 selector-9/10 bridge stores, but did
not replay this iOS control-bank operation.  It is **not** safe to translate
that observation into a bulk write list: the function chooses bit 31 from a
platform condition, and its relation to the already-running Linux PMGR state
is unknown.

## Decision

Do not perform a Linux/Pongo control-bank replay or another RGX identity read.
The next useful work is a static call-path trace that identifies which
AppleT7001PMGR virtual/platform operation reaches `c8a01c`, and whether it is
specific to the G4G clock action or a coincident board setup action.  Only if
that trace establishes a bounded GFX dependency should a hardware test be
considered.  The first safe hardware observation, if required, is a
read-only before/after capture of the already-mapped control-bank words on
iPadOS—not a write from Linux.

## Evidence and limits

* `research/2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md` records
  the 49 completed writes.
* `research/2026-11-17-j81-power-callback-ordinary-store-gap.md` confirms
  the power callback adds no additional ordinary store beyond the covered
  window.
* `artifacts/live/private/gpu-offline/ios15pmgr-vtable-bridge.c` decompiles
  `+0x980`, `+0x988`, and `+0x990`.
* `artifacts/live/private/gpu-offline/ios15t7001pmgr.c` decompiles
  `c8a01c` and its control-bank loop.
* `research/2026-11-08-j81-ios15-bcc56c-timing-accounting.md` and
  `research/2026-11-08-j81-ios15-soc-tuner-device-sets.md` bound the timing
  helper and gated counter read.

Static code and captured method arguments do not establish physical register
semantics, runtime ownership, or causality for the RGX read stall.
