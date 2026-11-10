# J81 iOS page-5 timing control

Prepared and run 2026-11-10; see the [hardware result](../../2026-11-10-j81-page5-capture-results.md).
The cross-OS capture
observed `0x20e005004 = 0x40000000` after iOS identity and `0` after the
Linux GFX/GPC control, on separate boots. This probe reads the same iOS
location earlier: immediately after the first GFX clock-provider call
returns, before the caller proceeds to GPC setup and identity. It tests
whether bit 30 is already set at that earlier boundary. It does not prove
what controls the bit or that the bit is causally related to GPU access.

The probe extends the host-tested [poll comparison](../j81-pollcompare/README.md).
If the PMGR poll identified the GFX region/offset/instance and saved the
provider object, and interrupts are enabled after the provider returns, it
logs `PAGE5-early-before`, calls that object's existing read method once with
region 0, offset `0x5004`, instance 0, then logs `Q=xxxxxxxx`. The object
pointer's lifetime is inferred, not independently established. A missing
marker or missing result is inconclusive. The identity hook continues to
log the previously observed GPC poll and identity markers. The device-tree
cross-reference to physical `0x20e005004` is not an independent iOS mapping
measurement. This introduces one extra undocumented MMIO read; a stall,
reboot, read side effect or lost early-boot log is possible.

Module local path:
`artifacts/live/private/j81-ios-page5early-probe/page5-early4`.
SHA-256 `924d70cc888c01fe9ef7a8e76246b6cc67524aa5745b2814f556631bdd94f2a2`.
It was built from this source in the Pongo checkout pinned in the
[thread probe](../j81-thread/README.md), registering
`j81_page5early_capture` and using `KPF_CFLAGS=-DJ81_PAGE5EARLY_DEVICE_BUILD`.
Nine exact sites and the kernel UUID are checked as a group. The target
19H394 image passed the host KPF harness; each independently missing or
duplicated signature and a wrong UUID was rejected. Native ARM64 host
simulations tested the fixed method arguments, marker/result, first-provider
one-shot and the no-PMGR-context skip. The final binary's fixed `0x5004`
call sequence was checked. Host tests do not validate live object lifetime,
MMIO safety, scheduling or log persistence.

No page-5 write or Linux GPU-core read follows automatically from the
result. Full device log archives may include personal information and must
remain private.
