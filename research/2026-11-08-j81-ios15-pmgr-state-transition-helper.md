# J81 iOS 15 PMGR state helper: a bounded offline lead

Date: 2026-11-08. Static follow-up in the local iOS 15.8.8 `ApplePMGR`
Ghidra project. No device, firmware, or MMIO access.

## Verified result

The PMGR slice contains a reusable indexed-state transition path beyond the
G4G/provider call boundary. `FUN_fffffff006bc6c20` validates a state-table
index and device-record index, checks the per-device state mask, and dispatches
through the PMGR vtable at `+0x980` to obtain the state word. Its companion
`FUN_fffffff006bc6ed8` reads the same state, compares the requested low-nibble
state and associated flags, and only calls the transition operations when the
requested state differs. It uses vtable `+0x988` to issue state-word updates
and `+0x990` for a timed transition/poll operation (arguments include mask
`0xf0`, the desired state shifted by four, and timeout `0x2ee00`). Thus the
known iOS 15 PMGR code has an explicit state read/compare/write-and-wait
mechanism; the existence of this helper alone does not prove GFX invokes it.

The helper is used by PMGR initialization/reconciliation code and other device
state operations in the same binary. The decompiled initialization routine
`FUN_fffffff006bbf7a4` calls it while walking configured state records. Static
references do not bridge the G4G provider clock callback to this helper or to
the iOS 15 `AppleT7000` GFX special-action handler. The current provider-call
boundary therefore remains real: do not claim the GFX callback reaches this
path based only on the shared PMGR state data or matching offsets.

## Why it matters to the hang investigation

The iOS 8.1 reconstruction gives GFX's clock edge a PMGR state-100 request to
state 15 followed by bridge selectors 9 and 10. The iOS 15 binary independently
contains a state transition engine with explicit current-state comparison and
bounded transition operations. If a future cross-kext dispatch trace proves
that the iOS 15 GFX callback uses this helper, it will be possible to compare
its state-word semantics and timeout/flag handling with the iOS 8.1 path, then
with Linux test4's generic PMGR operation. At present this is a candidate
comparison point, not evidence that an extra write or reset precedes the
stalled RGX read. It does not justify another hardware read or register replay.

## Evidence and limits

Evidence is in ignored local artifacts:
`artifacts/live/private/gpu-offline/ios15pmgr-state-read.c` at
`0xfffffff006bc6c20` and `0xfffffff006bc6ed8`, and
`ios15pmgr-init.c` / `ios15pmgr-device-calls.c` for callers. In particular,
these are generic PMGR routines, not a proven AppleT7000 GFX callback target.
The required next offline step is resolve the iOS 15 provider/platform-function
vtable bridge from the G4G receiver to an `AppleT7000` callback; only then can
this transition helper be associated with GFX.
