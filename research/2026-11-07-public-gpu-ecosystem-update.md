# Public A8X / PowerVR ecosystem update (2026-11-07)

Read-only review of current public OrchardLinux, Project Cascadia and Mesa
sources, compared with the September 12 ecosystem check in
`j81-long-term-subsystems.md` and the November 6 J81 GPU boundary note.

## Findings

- **Orchard now lists J81/J82 as experimental device targets and has J81/J82
  device-tree support.** Its generated compatibility matrix identifies T7001,
  the boards, and iOS 14.8.1 build `19H422`; the project README still says the
  currently supported iPad is J71b and explicitly says GPU acceleration is
  unavailable. This adds Orchard device-description/DT material to compare
  against our local J81 DT, but it is not evidence of an Orchard GPU driver or
  a new GPU sequence. The matrix says experimental, not install-ready.
- **Cascadia's A5 GPU is now far beyond the old Phase 1 assessment.** Its
  current iPad mini 1 documentation reports a working Linux SGX543MP2 driver,
  2D acceleration, a custom Mesa Gallium driver, GLES 1.1/2.0 and desktop GL
  2.1, with reported dEQP and piglit results. The kernel driver boots the
  iOS-provided GPU microkernel; Cascadia's own USSE/PDS programs and Mesa
  compiler implement userspace. This is a strong proof that a full Apple
  PowerVR-era Linux stack can be reverse engineered, but SGX543MP2 is the
  older SGX architecture; it does not supply a reusable Rogue/Series6XT driver
  for A8X's GXA6850.
- **Mesa's current public support status remains a hard blocker for an
  off-the-shelf A8X stack.** Mesa lists GX6650 BVNC `4.46.6.62` as unsupported
  and inactive, while GX6250 `4.40.2.51` is partial/inactive with instability
  and corruption expected. Product-name similarity is insufficient: Mesa
  specifically warns the BVNC must match. Neither entry is GXA6850, whose
  exact BVNC remains the gate.

## Action for J81

1. Compare Orchard's J81/J82 device data and DT against our own; use only
   verified T7001 data to reconcile names/resources, not as proof of GPU-safe
   addresses or initialization order.
2. Keep the immediate GPU work at the existing safe boundary: resolve the
   zero GPC state via offline iOS bring-up-order analysis and a checkpointed,
   read-only prerequisite-state observation. Do not infer that Cascadia's
   iOS-microkernel approach is safe to try on A8X before the J81 firmware,
   power/clock/reset and DART contract is established.
3. Once the J81 BVNC is read safely, compare it against Mesa's BVNC tables and
   device-info/firmware data. Expect a new hardware-specific implementation;
   no public source reviewed here supplies it.

## Sources

- Orchard overview and current stated support: https://github.com/OrchardLinux/orchard
- Orchard generated device compatibility matrix: https://github.com/OrchardLinux/orchard/blob/main/docs/compatibility.md
- Cascadia A5 device status and GPU milestones: https://github.com/rzxvx/Project-Cascadia/blob/main/devices/a5/README.md
- Cascadia GPU/Mesa architecture and bring-up documentation: https://github.com/rzxvx/Project-Cascadia/blob/main/devices/a5/docs/GPU.md
- Mesa PowerVR support/BVNC matrix: https://docs.mesa3d.org/drivers/powervr.html

No iPad was accessed; this update uses public source repositories and project
documentation only.
