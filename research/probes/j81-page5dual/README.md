# J81 iOS same-checkpoint page-5 pair

This probe samples region 0 offsets `0x5000` and `0x5004` in that order,
immediately after GPU identity on a temporary iPadOS 15.8.5 19H394 boot.
The PMGR object's existing `+0x980` read method is used twice; no page-5
write is added. The association with physical `0x20e005000` and
`0x20e005004` is inferred from the captured Pongo ADT, not independently
verified on iOS. The saved object's lifetime is inferred. The samples are
consecutive, not atomic, and do not prove clock state or causation.

`PAGE5-before` precedes the reads; once both have returned, `0=xxxxxxxx`
and `4=xxxxxxxx` report the respective values. A missing result is
inconclusive. If the first or second read stalls, neither result line is
guaranteed, and boot logs may be lost. A boot-local atomic claim prevents
repeating the pair. The hook requires the observed PMGR poll, a saved
object and enabled interrupts. Earlier individual reads succeeded, but
these undocumented accesses may have side effects, hang or reboot iPadOS.

The module is `artifacts/live/private/j81-ios-page5dual-probe/page5-dual`,
SHA-256 `c866b37a24c50dde3f861436fd16a5ed32b0731d796bec61cb29cb2b67488ae1`.
Built from the [pinned Pongo checkout](../j81-thread/README.md), registering
only `j81_page5dual_capture` in the component array, with
`KPF_CFLAGS=-DJ81_PAGE5DUAL_DEVICE_BUILD`. The target UUID and all nine
unique instruction signatures remain guarded. Native host tests checked
the exact read arguments and order, one-shot behavior and missing-PMGR
skip; the KPF harness accepted the target and rejected nine individually
missing and nine duplicate signatures and a wrong UUID. Final-binary
disassembly shows both fixed offsets in sequence. These checks do not
validate the live object, timing or MMIO safety. No hardware run yet.

Run on a fresh DFU device with the existing temporary rootless boot flow:

```sh
sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-page5dual-probe/page5-dual --debug-logging
```

Verify the checksum immediately before use. Boot archives can contain
personal data and must remain private. Interpret either value as a snapshot,
not as a reason to write page 5 or repeat the stalled Linux GPU-core read.
