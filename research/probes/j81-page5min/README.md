# J81 iOS reduced middle page-5 probe

Offline-built variant of [the intermediate probe](../j81-page5middle/README.md), targeting iPadOS 15.8.5 19H394. It retains the prior early and late reads and samples PMGR offset `0x5004` at successful GPC poll; the buffered middle result is logged as `M=xxxxxxxx` after identity. Missing output is inconclusive.

The new middle hook saves x0–x30 and NZCV in a 320-byte stack frame and uses no FP/SIMD instructions. It reads only if the current PMGR method pointer equals the KASLR-adjusted address `0xfffffff006bd0478`. The inspected 19H394 matching method and its successful-path helpers use integer instructions and a direct 32-bit mapped load. A mismatched method skips the middle read. Bounds errors follow the method's error path. Kernel UUID and nine patch signatures are also checked. The earlier clock and identity hooks still use SIMD and retain their larger frames; this variant does not eliminate SIMD from the entire probe.

Private module `artifacts/live/private/j81-ios-page5min-probe/page5-min4`, SHA-256 `3ce3a82ecca142355244c81b0df315de49116d27c26459c35be0f5f1761a30ae`, built with `KPF_CFLAGS=-DJ81_PAGE5MIN_DEVICE_BUILD` and component `j81_page5min_capture` using the same Pongo checkout as the paired probe.

Exact-kernel KPF tests accepted the target and refused each of nine missing or duplicated signatures and a wrong UUID. Native ARM64 simulations exercised early/middle/late arguments and ordering, busy polling, wrong thread, wrong method target, absent context, IRQ masking, one-shot behavior, and flags on skip paths. `test_register_layout.py` checks the middle save/restore layout and lack of SIMD instructions. These checks do not establish real call-context stack headroom, object lifetime, mapping validity, unrelated outer locks, actual saved-register values after the real call, or MMIO safety. The full capture can perturb timing; an undocumented read may have side effects, hang or reboot the device, and the buffered result may be lost. The probe has not run on hardware and remains subject to review of these constraints.

The hardware run completed with early `0`, buffered middle `0x40000000`, and
late `0x40000000`; GPU firmware startup was subsequently reported. See the
[complete capture](../../2026-11-10-j81-page5-capture-results.md#reduced-middle-probe-change-observed-by-the-gpc-poll).
