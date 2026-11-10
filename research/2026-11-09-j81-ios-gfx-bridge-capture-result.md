# J81 iOS 15.8.5 GFX bridge-capture hardware result

2026-11-09. A fresh DFU boot used palera1n rootless with the
[bridge-capture module](2026-11-09-j81-ios-bridge-probe-build.md), SHA-256
`dc7dbcb245dc474310ebb2a8f8b200989a5d747bf686c33cc448b1ce3312e59a`.
The iPad booted to iPadOS. The first archive request got USB mux error -8;
a cable replug while unlocked restored device service and allowed capture.

The filtered kernel archive contains the following events from boot UUID
`07633D06-E463-4CEE-ABD0-3EA0C8B739EF` (local times):

```
23:14:17.297 AGXk: Starting GPU driver. Available features: release
23:14:17.446 AGXk: Starting GPU driver. Available features: B0
23:14:17.454 AGXk: Probing - Detected G4G A1 [...]
23:14:17.572 AGXk: ... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`B0` is the probe's drain message with overflow flag clear and **zero
selector/offset/value records**. Its presence is positive evidence that the
clock-call wrapper ran, returned from the original provider and reached its
logger with IRQs enabled. It is not a log transport failure. The GPU probe and
firmware boot messages show iOS continued through those reported stages.

The writer hook records only selector 9 or 10, state argument 15, at the
inspected `bd3e58` dispatch, while the G4G clock-provider call is in flight.
The empty result therefore says the probe recorded no matching dispatch in
that window. It does not prove that no relevant bridge write happened before
the window, elsewhere, under another selector or state, or that the writer
hook executed as expected on hardware. The host patchfinder only installs the
two hooks together, but there was no independent on-device positive writer
hook control and no direct runtime capture of the patch receipt.

A plausible explanation is that GFX's cached state was already on and the
provider did not initiate an increasing transition. The static iOS provider
analysis documents an unchanged-state early return; this boot did not record
the cache value or transition decision, so that explanation is **not yet
verified**. The capture does not show whether the values of selectors 9/10
were already present and does not explain the Linux RGX access failure.

Next offline, inspect the provider entry/early-return path and select an
observational hook that reports the GFX cached/requested state and which
branch executes. A stronger follow-up could capture selector writes outside
the narrow window or inspect already-readable state on iOS, but needs a
separate evidence-based design. Do not treat this empty capture as a complete
trace or repeat the same experiment expecting a different result.

Private `artifacts/live/private/ios-logarchive-j81-bridge-01/` holds the
archive and filtered `bridge.json`; the unfiltered archive may contain
personal system information. No GPU or PMGR register was newly read by this
custom probe.

After the archive was captured, the host requested a normal restart. The iPad
reappeared through device service and reported build `19H394`. No DFU-to-Linux
recovery test was performed in this round.

Offline follow-up: [a wider capture and cached-state decision probe](2026-11-09-j81-ios-wide-bridge-probe.md)
has been built and host-tested; it has not been run on hardware.
