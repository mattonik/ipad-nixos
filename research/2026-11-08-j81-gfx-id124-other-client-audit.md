# J81 GFX gate ID 124: other-client audit

Date: 2026-11-08. Offline review of the local 12B410/iOS 8.1 and iOS 15
kernelcache artifacts and the J81 ADT. No device, boot, or MMIO access.

## Finding

No Apple service besides the GPU service is shown requesting J81 GFX gate ID
124 before the G4G probe. The stronger static result is that the captured ADT
has only one direct declaration of clock gate 124: `/arm-io/sgx` with
`clock-gates = [124]` (and `power-gates = [124]`). The recursive property walk
also includes display, DART, scaler, ISP, JPEG, VXD, storage, and PCIe nodes;
none has clock gate 124. In this provider API, clients pass a gate-array index,
not the ID itself. Therefore a service matching some other node's provider
and calling index 0 does not become a request for `sgx` ID 124.

The 12B410 `__PRELINK_INFO` match inventory independently narrows the
potential direct client. The cached `gpu,t7001` and `sgx,t7001` strings each
occur once, together in the `com.apple.AGX` `AGXG4G_A0` personality; it matches
`AppleARMIODevice`. The other AGX personalities in this cache target T7000 or
older GPU variants, not T7001. The local disassembly confirms the G4G probe
retains that matched `sgx` provider and calls its clock slot `+0x560(1, 0)`
before its power slot and before GPC setup / RGX identity. The display driver
is a separate `AppleARMIODevice` match for `adbe0,t7001`; its provider list is
`disp0`'s `[112, 118, 116]`, not 124.

The iOS 15 G4G disassembly agrees on the probe-side bound: before the first
RGX identity read it has one explicit provider clock enable, at
`provider +0x568(1, 0)`, then one power enable at `+0x570(1, &out, 0)`.
The slot shift is inferred from the iOS 8.1 mapping and argument shape. This
shows no second clock request within that G4G pre-ID path; it does not census
other iOS 15 services.

## What is closed and what remains open

For the captured J81 configuration and 12B410 prelink matches, the plausible
same-node static client is AGX/G4G itself. The offline evidence does not show
another declared Apple provider client that selects `sgx` gate-array index 0.
It therefore closes the ADT/matching-based alternative as a documented
candidate, rather than leaving the earlier broad claim that any ADT consumer
is only "unlikely."

It cannot prove a boot-time negative: a service could acquire the `sgx`
provider indirectly, use a framework-mediated lookup not expressed in a
personality match, or issue a direct ID-124 request through an untraced path.
The available artifacts have no 12B410 service-start timeline. Thus the
strict question “was ID 124 requested by another client before G4G's probe?”
remains unproven at runtime. Do not promote this static inventory to a claim
that G4G's request was definitely the first request or a 0-to-1 reference
edge. Startup's zeroed counter and tracked PMGR state are separate conditions.

## Evidence

- `artifacts/live/private/gpu-offline/ios81-dt.json`: recursive `clock-gates`
  inventory; `/arm-io/sgx` is the only 124 entry.
- `artifacts/live/private/gpu-offline/kernelcache`: original 12B410 prelink
  metadata. A bounded raw match check finds exactly one `gpu,t7001` and one
  `sgx,t7001` string, in the AGX G4G personality; this is not an audit of
  framework-generated or indirect runtime matches.
- `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` and
  `research/2026-11-07-j81-gpc-provider-object-binding.md`: G4G receiver,
  matched provider, clock slot and gate-array selection.
- `research/2026-11-07-j81-disp0-record-consumer-trace.md`: AppleMobileADBE0
  matches `adbe0,t7001` and uses `disp0` clock indexes 0–2 (IDs 112, 118, 116);
  its ID-28 PMGR dependency is a record dependency, not a gate-ID-124 request.
- `artifacts/live/private/gpu-offline/ios15-agx-disasm.txt` and
  `research/2026-11-08-j81-ios15-g4g-pre-id-clock-power.md`: the single
  explicit iOS 15 pre-ID clock request and its inferred slot mapping.
- `research/2026-11-07-j81-gfx-clock-reference-startup-audit.md`: the
  initialized reference count, tracked-state caveat, and consequences of a
  genuine first edge.
