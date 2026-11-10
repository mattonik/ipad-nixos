# J81 PMGR page-5 comparison probes

Prepared 2026-11-10. These probes have not yet been run on hardware. They
read an undocumented PMGR block and can hang or reboot either OS; the
registers may have read side effects. A prior bounded LLB analysis found no
direct page-5-to-GFX selector path, so different values would be a lead, not
proof of a GPU prerequisite. See [page-5 dataflow](../../2026-11-09-j81-llb-page5-clock-dataflow.md).

## iOS

The source extends the [poll comparison](../j81-pollcompare/README.md). After
the original PMGR poll and both RGX identity reads complete, it saves the
known PMGR object's pointer from the matching GFX poll and makes **one extra**
read through that object's existing `+0x980` virtual method, region 0,
instance 0, offset `0x5000`, `0x5004` or `0x5008`. The captured J81 Pongo
ADT maps region 0 to the PMGR aperture at physical `0x20e000000`; this
cross-reference is not an independent live iOS physical-map measurement.
The PMGR singleton's lifetime at the later identity hook is inferred and
not independently validated. If no matching PMGR poll was seen, or its
object/method pointer is missing, the extra read is skipped. A boot-local
atomic flag prevents a repeat, even if the identity method is called again.

Each binary is built for exactly one offset. The probe logs `PAGE5-before`
immediately before its extra call and `Q=xxxxxxxx` after it returns. These
are kernel log messages: **if iOS hangs before log retrieval, neither marker
is guaranteed recoverable**. A `Q` value is a snapshot after GPU identity,
not proof of bootloader history or the state at Linux's later failing read.
The original identity/poll values and all-selector buffer are retained.

Local ignored binary SHA-256 values:

| Offset | File under `artifacts/live/private/j81-ios-page5-probe/` | SHA-256 |
| --- | --- | --- |
| `0x5000` | `page5-0` | `c4c59cb31f5eb50ee358deba195284d0d47fb6ed8e0ebf94b4ab9b7f1cf46d5f` |
| `0x5004` | `page5-4` | `889c456e18abc334a8e8bff11bf69dd86e31a6f6d2b4b909a249aff8c5975745` |
| `0x5008` | `page5-8` | `43629e805d0865b660f72b2e91d3f130dc0273b8e69d70461440d70d2fc6c37` |

The fixed offset in each final binary was independently checked against the
machine-code instruction sequence. The 19H394 KPF host harness accepted the
expected image and refused each of nine missing or duplicate signatures and
a wrong UUID. Native host simulations exercised each offset, virtual-call
arguments, log messages, one-shot behavior and missing-PMGR skip. Simulated
calls do not test the iOS object's lifetime, MMIO or device timing. The
source uses the Pongo checkout pinned in the [thread probe](../j81-thread/README.md);
register `j81_page5_capture` and build with
`KPF_CFLAGS='-DJ81_PAGE5_DEVICE_BUILD -DJ81_PAGE5_OFFSET=0'`, replacing 0
with 4 or 8. Unsupported offsets are rejected at assembly time.

## Linux

The complementary module is `kernel/page5-read-once`, with a pinned
J81/4-KiB/kernel/RAM-boot preflight in `boot/j81-page5-read-once-run.sh`.
It calls `readl` on the PMGR page only after a
host-acknowledged checkpoint. The PMGR platform driver already owns the
containing resource, so it uses a temporary shared `ioremap` rather than
claiming that resource. The mapping itself is not enforced read-only; the
module issues no writes. One module read is permitted per
boot; the module is pinned after loading. The 20-second watchdog may reboot
the iPad on failure, but a hardware stall can still need DFU recovery.

`boot/j81_page5_capture.py` preserves the host checkpoint before issuing the
`READ` acknowledgement and records the result. Host tests cover the three
offsets, wrong-device and bad-offset guards, the one-shot and mapping-failure
paths, checkpoint ordering, and watchdog protocol. The AArch64 module was
built on the Linux builder against the same kernel build tree used by the
previously successful MCC module, and its vermagic matches. The build warned
that `pahole` was unavailable, so module BTF was not generated. The static
watchdog and the module are in `artifacts/live/private/j81-page5-linux-bundle/`
alongside the runner, host capture script and checksums. The running kernel
notes and final hashes must still be verified before use. Module loading and
the page-5 read have not been tested on hardware.

Linux and iOS snapshots are at different instants and may differ for reasons
unrelated to GPU. No register write or repeated stalled RGX read follows
automatically from a difference.
