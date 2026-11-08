# J81 PMGR gate function phandle provenance

Offline artifact comparison, 2026-11-08. No device access or firmware execution.

## iOS 15 capture

The live Pongo ADT at
`artifacts/live/private/gpu-observations/20261106T060741Z-pongo-adt.adt`
includes boot argument `original-base-os-version=19H386`. Its `arm-io`
properties encode `function-clock_gate` as selector `clkG` and
`function-power_gate` as selector `pwrG`; both reference ADT phandle `0x1a`.
The node with `AAPL,phandle 0x1a` is named `pmgr`, with
`compatible=pmgr1,t7001` and `device_type=pmgr`. This establishes the target
node and selector names for this capture.

## Separate iOS 8.1 artifact

`artifacts/live/private/gpu-offline/ios81-dt.json` records the same two
selectors with phandle value `335544320` (`0x14000000`). This is the value in
that decoded iOS 8.1 artifact; do not substitute it for the iOS 15 capture's
phandle `0x1a` or infer a shared literal encoding from the two artifacts.

## Object and callback identity limit

The iOS 15 kernelcache contains strings for
`ApplePMGRFunctionClockGate` and `ApplePMGRFunctionPowerGate`, as well as
`AppleARMPerformanceControllerFunctionClockGate` and
`AppleARMPerformanceControllerFunctionPowerGate`. These are candidate class
names only: string presence does not map either ADT selector to a class or
prove that class created the cached objects. The available
`AppleT7001IO::start` evidence shows it resolves/registers the two ADT
functions; wrappers call the retained function objects indirectly at `+0x80`.
The concrete object creator, dynamic classes, and `+0x80` callback addresses
remain unresolved in the available kernelcache metadata and disassembly.
