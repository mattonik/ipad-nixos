# J81 installed iPadOS 15.8.5: kernelcache comparison

2026-11-09. The user reports iPadOS **15.8.5, build 19H394** on the iPad.
This is a user-reported build; no live kernel bytes were acquired. The J81
board association comes from the existing project records.

## Source and verification

The iPad5,3 [IPSW Downloads metadata](https://api.ipsw.me/v4/ipsw/iPad5,3/19H394)
identifies an Apple-hosted 15.8.5 restore archive. Orchard's `remote_ipsw`
read its manifest and J81 kernelcache by HTTP range from
[Apple's restore archive](https://updates.cdn-apple.com/2025FallFCS/fullrestores/082-67137/2FF7F5F3-3900-4F6D-BBDF-A68EEBE7B83F/iPad_64bit_TouchID_15.8.5_19H394_Restore.ipsw),
without downloading the full archive. The manifest reports ProductVersion
`15.8.5`, ProductBuildVersion `19H394`; both J81 erase and upgrade identities
select `kernelcache.release.ipad5b` with SHA-1 digest
`d92daafde260ba8823b45cd429346fa8d10648a3`. The extracted raw member
matches that digest and has SHA-256
`05c2a843dc8f2447cdaf91fac1b0d832b3ccd06894c903750c948c9c09c794f5`.
Orchard's decoder produced a 42,549,248-byte Mach-O with SHA-256
`c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`.
This establishes its association with the archive manifest; it does not
independently hash the complete IPSW or verify the running device's bytes.

## Comparison with the 19H422 analysis

The 19H422 decoded cache SHA-256 is
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
The full decoded files are the same length but differ in 8,860,359 byte
positions. However, each of the following previously extracted code slices
is byte-for-byte identical at the same file offset in the two decoded files:

| Slice | File offset | Length | SHA-256 |
| --- | --- | --- | --- |
| AGX code | `0x1b18000` | `0x45960` | `9543debbf2d4bdb80c44cd2c6e9d2bb651631ce9d3561cd8b63c7bd9f0269d50` |
| ApplePMGR code | `0x2065000` | `0x34a4c` | `8f1e2fbf2d9755218221c64f655bb5ea233b264d5baf9bb9b0c0c0d38f52324a` |
| AppleT7001PMGR code | `0x2134000` | `0x2f28` | `0400d6b1be4ee2b724250e20a6a46c1166361432644453a658a05d6f9fe547ff` |
| AppleT7000 code | `0x213b000` | `0xaadc` | `ac836c6a58217bbf3be05d76d57d4faadec9d188b251ac54dc533e5a43eda4a0` |

This carries the previously disassembled instructions, including the G4G
pre-ID path and the inspected PMGR routines, over to this extracted 19H394
image. It does not establish identical vtables, data, configuration,
dependencies, runtime bindings, or other kernel components. It also does
not establish a working iOS boot or GPU trace.

For each previously chosen clock, GPC and identity site, the old 16-byte
signature has exactly one match in the entire new decoded file, at the same
file offset (`0x1b2f918`, `0x1b2f994`, `0x1b47b54`, respectively). Each
4,096-byte window starting at those offsets is identical too. This check is
specific to these files; it is not proof the signatures are safe patch sites.

## Match-only host test

The previously built PongoOS match-only KPF harness was run against the
19H394 decoded cache. It exited 0 and printed
`J81_MATCH_ONLY clock=1 gpc=1 identity=1` and `KPF: Applied patchset`.
The harness also printed the existing `Dounmount failed to find second call
for parent_vp` diagnostic. The input SHA-256 remained unchanged after the
run. As in the [original feasibility record](2026-11-09-j81-ios-startup-trace-feasibility.md),
stock KPF changes a private in-memory mapping; this is only a host matcher
test, not a bootable GPU hook or proof of all stock patch behavior.

Next, design and validate an observation buffer, safe code relocation and
retrieval on the host before considering a boot-only instrumented test.
The installed build report narrows the target, but the actual on-device
kernelcache and successful recovery path remain to be independently verified.
No iPad or GPU MMIO access was performed in this comparison.

Private artifacts: `ios1585-19H394-BuildManifest.plist`,
`ios1585-19H394-kernel.im4p`, `ios1585-19H394-kernel` under
`artifacts/live/private/gpu-offline/` and `j81-match-19H394.log` under
`artifacts/live/private/j81-kpf-match-only/`.
