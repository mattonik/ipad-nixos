# Orchard iOS GPU capture portability: J81 / iOS 15

Offline review of the Orchard checkout's `gpu/tools/a10/ios-capture` tree; no device was connected and no Orchard files were changed.

## Assessment

This is a useful reference for the *method* of capturing an iOS Metal submission, but it is not a portable A8X capture tool. The build scripts target arm64 iOS 16.0 (`build-cli.sh`, `build-app.sh`, `overlay.py`), while the offline compiler path explicitly targets `applegpu_g9p` and AIR iOS 17 (`offline/build.sh`). J81 is A8X/T7001 with PowerVR GXA6850, not A10/G9P; the offline USC needles and G9P binary therefore cannot be carried over as A8X GPU code evidence. See `research/hardware.md` and the project's A10-specific source comments.

## Runtime and trust assumptions

- `app.m` is the relevant foreground-app pattern: its comment says non-app processes are denied GPU access. It also calls `capture()` with the full-mode defaults. In `capture.m`, full mode walks process VM regions, reads and saves GPU-tagged regions and scans other readable memory for needles; the source itself records that a broad scan once panicked the device. This wrapper is not a safe first-run path as written.
- The lower-risk existing mode is `--light`: GPU-tagged regions only and no needle search. The app wrapper does not select it. Even this is a privileged, invasive diagnostic and should be treated as a bounded experiment with host-side capture and recovery ready.
- `iohook.m` patches IOKit entry points in the process using writable/executable page transitions, trampolines, and instruction-cache invalidation. When `gHookDir` is set, it `_exit(0)` after a user-client trap by default because patched IOKit pages fault on completion. The default app calls full `capture()` without setting `gHookDir`, so that hook takes its pass-through path; it does not establish that the app UI will always update, since full scanning itself has a source-recorded device-panic history.
- `entitlements.plist` requests platform-application, no-container/no-sandbox, dynamic-code-signing, `get-task-allow`, and private IOKit user-client entitlements for AGX/IOGPU/IOSurface. The source comments say those client entitlements are needed to open the accelerator. A normal ad-hoc signature does not establish that iOS 15 will accept these private entitlements; actual acceptance depends on the jailbreak/launch environment and must be verified on the target.
- `session.py`/`overlay.py` assume palera1n, a root binpack telnet service, root SSH setup, macOS Xcode tools, and external `resize-apfs` helpers. This is a development boot-and-control workflow, not a generic iOS app installer. `session.py` also disables SSH host-key checking, so its transport is only defensible on its local USB-mux loopback tunnel.

## Minimal safe portability validation

1. Treat the task as a fresh J81/PowerVR investigation: do not copy G9P shader needles, `gpuAddress` assumptions, IOKit class names, or A10 capture conclusions without evidence.
2. The public-API-only probe at `boot/metal-device-info.m` calls `MTLCreateSystemDefaultDevice()` and prints the device name. It compiled and linked as arm64 with deployment target iOS 15.0 against the installed iPhoneOS 27.2 SDK, with `-Werror=unguarded-availability`; the Mach-O load command reports minimum OS 15.0. The output was temporary and was not signed or run. This confirms compiler/linker compatibility for this tiny probe, not device runtime availability.
3. The A10 source's `MTLBuffer.gpuAddress` and `gpuResourceID` properties are iOS 16+ in the installed Metal headers, so omit them from an iOS 15 probe or guard them explicitly.
4. Establish that the iOS 15/J81 runtime exposes a usable Metal device and identify the actual accelerator user-client classes and entitlement/launch requirements from read-only evidence. Do not assume AGXDeviceUserClient or IOGPUDeviceUserClient applies to A8X.
5. Only after the small probe succeeds on target, make a separate capture variant that has explicit bounds, defaults to GPU-only/light capture, does not execute the broad address-space scan, and writes results before any submit path that may terminate. Capture the host-side log from the start; do not rely on the app UI returning after the trap.

This report does not establish whether iOS 15 on J81 has a Metal stack usable by the capture, whether the private entitlement set is honored, or which A8X user-client is appropriate. Those require SDK inspection and controlled target evidence.

## Orchard tool operation and iOS 15 gates

The source review below is read-only. It did not access an iPad or change Orchard.

### Verified from the source and local SDK

- `build-cli.sh`, `build-app.sh`, and `overlay.py` pass `-target arm64-apple-ios16.0`; the app plist also sets `MinimumOSVersion` to `16.0`. Thus these exact artifacts are explicitly iOS 16-only.
- In the installed iPhoneOS 27.2 Metal headers, `MTLBuffer.gpuAddress` (`MTLBuffer.h:112`) and `gpuResourceID` (`MTLComputePipeline.h:257`) are annotated `API_AVAILABLE(ios(16.0))`. `capture.m` uses GPU addresses to build needles and log resource addresses, and reads `gpuResourceID._impl` in compute/render logs. These public API availability declarations establish that those accesses need removal or availability handling for iOS 15; they do not by themselves establish device behavior on any iOS 15 release.
- The normal capture issues small Metal compute workloads, then enumerates its own VM regions with Mach APIs and saves GPU-tagged regions and (outside light mode) readable regions matching GPU-address/offline-code needles. The broad scan has a source comment noting a prior device panic.
- `--light` limits scanning to GPU-tagged regions and avoids needle matching, but the current source still references `gpuAddress` and `gpuResourceID` elsewhere in the compiled `capture.m`; choosing the flag alone does not make the binary iOS 15-compatible.
- The inline IOKit hooks rewrite ARM64 function entries, create trampolines, inspect pointer-like trap arguments, snapshot memory, and usually `_exit(0)` after a trap. Render mode keeps running after traps because one render may submit multiple times. The hook depends on the expected function symbols and instruction layouts; source inspection does not establish that those remain stable across OS/driver versions.
- `capture()` and `capture_render()` delete their output directories before creating them. `--peek` dispatches a shader that reads a caller-provided GPU address without bounds checking. These are concrete operational behaviors to account for when selecting a mode and output path.
- `app.m` wraps full capture in a foreground UIKit app; `overlay.py` only installs the CLI binary. `session.py` assumes a palera1n root telnet/binpack flow and provisions key-only dropbear reached over USB proxy ports. The source comments state the CLI process is denied GPU access, while the app is intended to obtain foreground GPU access; this privilege behavior is source-documented, not revalidated on target here.
- The offline `applegpu_g9p` shader compilation script targets AIR iOS 17.0. That offline artifact path is distinct from compiling/running the runtime capture and is A10-specific.

### Smallest proposed iOS 15 adaptation

For a raw/light capture only, the smallest code direction is to build a separate iOS 15 variant: lower the three deployment targets and app plist minimum, remove the `gpuResourceID._impl` logging, and conditionally omit the `gpuAddress`-based needle creation/logging. Keep only the GPU-tagged-region snapshots; this loses address-based region matching and resource-ID diagnostics. The `gpuAddress` API gate is verified in the current SDK, but whether iOS 15 exposes equivalent GPU addresses through the IOKit calls is unverified. If address correlation is required, a parser for the captured IOKit resource-creation replies is a possible route, but that parser and the iOS 15 ABI/selector behavior are hypotheses until validated against target evidence.

Changing the minimum version and API calls is not sufficient evidence that GPU access will work: the private entitlements, foreground-app requirement, IOKit hook layout, and A8X user-client identity remain runtime questions. No device run is implied by this note.
