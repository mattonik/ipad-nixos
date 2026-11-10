# J81 bridge attribution: remaining gap

Offline audit of existing 19H394 iOS captures and Linux test4; no new device
access. The [all-writer capture](2026-11-10-j81-ios-allwriters-result.md)
contains 93 writer calls: selectors 9 and 10 each have 33 entries, while
selectors 7, 11 and 6 have 10, 3 and 14. The later
[thread-attribution capture](2026-11-10-j81-writer-thread-result.md) found
the 66 selector 9/10 calls on the observed GFX provider thread and all 27
other calls on different threads. Those other selectors correspond in the
captured Pongo ADT to display, USB and ISP; this is association rather than
proof of the live caller. A dependency scheduled asynchronously is not ruled
out. The two iOS captures are separate boots; their counts are not a single
atomic event history.

The [corrected comparison](2026-11-10-j81-ios-corrected-bridge-result.md)
matched all 66 iOS pre-dispatch selector/instance/offset/value records to
Linux test4's before-store checkpoints, and Linux reached all after-store
checkpoints. On iOS the hook records a request before the writer is called;
it does not confirm completion. On Linux the helper prints the intended
value, not a readback. Only the first target address has independent Linux
readback; the other 65 operations do not prove persistence. See the
[test4 readback boundary](2026-11-07-j81-test4-raw-readback-boundary.md).

The 27 extra calls are therefore weak candidates for direct GFX steps, and
blindly replaying them is unsupported. The remaining bridge-specific gap is
whether the GFX-thread requests completed and left equivalent hardware state,
not whether their logged sequences match. A broader readback would itself
access undocumented registers and needs per-address safety and side-effect
analysis; a completed-store tracer would still need runtime mapping and
concurrency attribution. Either must be justified against the higher-value
provider and boot-state investigations before a hardware campaign.
