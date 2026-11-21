# PongoOS KPF toolchain on the Mac: verified

2026-11-21. Reference tree: palera1n PongoOS `e98323f8a09abd80fc4cbcd74dee023b91a1ec22` with newlib `f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8` (the same commits as
`2026-11-09-j81-marker-kpf-build-review.md`), cloned to `/Users/martinp/Work/Sandbox/ipadlinux/pongoos/PongoOS-e98323f` (outside the repo, 138 MB after the build; cold copy as a
32 MB tarball on the NAS: `pongoos-e98323f/PongoOS-e98323f-with-newlib-f9ea505.tar.gz` + SHA256SUMS).

Build (no extra installs; Apple clang 21 + iPhoneOS 27.2 SDK + Xcode make; no ld64.lld/llvm-objcopy/ldid needed):
`cd PongoOS-e98323f && make build/checkra1n-kpf-pongo IGNORE_SUBMODULE_HEAD=1 -j4` builds newlib, then the stock KPF module:
`build/checkra1n-kpf-pongo`, 127,808 bytes, Mach-O 64-bit kext bundle arm64, sha256 `c030aa574361080e1b05638042a0f5fa98822e42006cf32a28943d792e8f3da0` (unmodified baseline; not loaded on any device).

Still missing: the source of our run-3 base module `0a20ead8...` (pmgr-bisect v3, hook at the end of `ApplePMGR::start`, P0/P1 records). Only binaries survive
(`artifacts/live/private/j81-ios-pmgr-bisect-probe*`); all later iPadOS state probes are one-word patches of it (`boot/make_j81_ios_state_probes.py`). Sources that do exist:
`research/probes/j81-gpc-timing` (`j81_timing_capture.c`, `j81_timing_shell.S`, signature-checked trampolines, logger call) and the page5/perf probes. A NEW iPadOS probe with
arbitrary extra reads (e.g. the bridge words 0x201f00000/0x201f80000, a timestamp at the identity read) therefore means writing a new KPF component on that model; it can now be built here.
