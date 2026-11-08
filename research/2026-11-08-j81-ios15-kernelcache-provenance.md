# J81 iOS 15 kernelcache provenance

Offline check, 2026-11-08. No device access; this note records the
provenance check.

The local decoded cache `artifacts/live/private/gpu-offline/ios15-kernel` is a
42,549,248-byte arm64 Mach-O with SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`. It is
byte-identical by SHA-256 to the `kernelcache.release.ipad5b.macho` in the
archived NAS extraction for iPad5,3 build 19H422. The associated raw
`kernelcache.release.ipad5b` is 20,816,861 bytes, SHA-256
`69120a77d28dd8896d1426889ea4877773022698023e3c7af542ad1b09e59f59`, and
matches the local `ios15-kernel.im4p` byte-for-byte.

The extraction's `BuildManifest.plist` identifies ProductVersion `15.8.8`,
ProductBuildVersion `19H422`, and a J81 (`j81ap`) KernelCache path of
`kernelcache.release.ipad5b`. Its manifest Digest is SHA-1
`842581e2de9ad8b045a2614357c0038e13239ba3`; that digest matches both the raw
NAS cache and local `.im4p`. The NAS extraction record also associates this
cache with the 19H422 iPad5,3 restore IPSW and records archive SHA-256
`4de5c8c453328205b1e741faae218ee0f7848993334ff77f690c5a64a765a623`. The
large IPSW archive itself was not independently rehashed in this check; the
source association is verified through the archived extraction manifest,
matching raw cache digest, and matching decoded Mach-O.

The local Mach-O's embedded `__PRELINK_INFO,__info` identifies platform
version `15.8` and `DTPlatformBuild=19H402` (no `19H422` string was found in
that metadata). The kernel version is `Darwin Kernel Version 21.6.0: Fri Mar 6
21:01:38 PST 2026; root:xnu-8020.241.44~1/RELEASE_ARM64_T7000`.
`DTPlatformBuild` is platform/toolchain metadata in prelink kext dictionaries,
not the top-level OS `ProductBuildVersion`; its 19H402 value does not
contradict the independently verified 19H422 source IPSW association.

The separate live Pongo ADT capture records boot argument
`original-base-os-version=19H386`; that capture does not identify this
offline file's source build or prove which binary was running on the device.
The local cache's source IPSW association is verified, while its identity as
the exact binary running on a particular device remains unestablished.
