# J81 page-5 change: bounded iOS writer investigation

Offline review of the 19H394 five-point capture, its KPF hook sites, the
inspected iOS G4G disassembly, and PMGR vtable entries; no new hardware
access. This does not identify the cause of the GPU stall.

## What the existing trace narrows

In the 19H394 capture, `C=0` is sampled in the hook replacing the original
`mov w8,#0x11`, just before the state-request store. `M=0x40000000` is
sampled in the hook replacing the branch after the successful GPC poll. The
samples are buffered and printed later in a different order. The captured
GPC poll value is `1`; firmware boot was reported. See the
[five-point result](2026-11-10-j81-page5-capture-results.md#gpc-control-boundary-transition-after-control-sample).

The original 19H394 instruction sequence at the two sites is independently
matched by the KPF signatures and, between those sites, is equivalent to:

```text
mov  w8, #0x11
str  w8, [GPC_base, #0x1000]
loop: ldr w8, [GPC_base, #0x1000]
      tbnz w8, #4, loop
```

There is no ordinary function call in that original same-thread path between
the state store and successful poll. This rules out attributing an additional
*direct same-thread call in that short original sequence* to the change. It
does not rule out interrupt handlers, concurrent CPUs, firmware, autonomous
hardware, a delayed earlier action, or probe/read effects. The injected hooks
and PMGR method calls add instructions and time; the iOS `M` read is after the
poll, not simultaneous with it. The conditional GPC control stores occur
before `C`; the marker alone does not prove they executed or persisted.

## A bounded software-writer lead

> Correction: `+0x988` and `+0x998` use different mapping tables, so the
> same numeric region/offset filter does not identify the same address for
> both. See the [writer mapping audit](2026-11-10-j81-page5-writer-mapping-audit.md)
> before implementing the trace described below.

In both local 19H422-associated and 19H394 kernel images, the static
AppleT7001PMGR instance vtable candidate at `0xfffffff006fe5e28` has:

| Slot | Candidate target | Observed static role |
| --- | --- | --- |
| `+0x980` | `0xfffffff006bd0478` | bounds-checked mapped 32-bit read |
| `+0x988` | `0xfffffff006bd04f0` | bounds-checked mapped 32-bit write |
| `+0x998` | `0xfffffff006bd3d38` | mapped 32-bit writer used by the captured bridge-dispatch path |

The runtime PMGR object's actual class and physical mapping are not
independently verified. In the 19H394 image, the first 44 bytes at `bd04f0`
are unique as a byte sequence; the first 24 bytes at `bd3d38` are unique.
A short 24-byte prologue at `bd04f0` occurs 49 times, so it is not by itself
a safe unique hook signature. Uniqueness is a static image scan, not proof of
correct patch placement, function boundaries, branch relocation or runtime
reachability.

The existing `j81-page5control` writer hook observes a dispatch within the
clock-provider window; it is closed before `C` and does **not** trace all
page-5 stores between `C` and `M`. Therefore its records cannot answer whether
another thread calls either generic PMGR writer in that interval.

A possible next iOS probe would retain the proven `C` and `M` sampling hooks,
use a bounded all-thread buffer to record calls to the generic PMGR writer
for region 0, offset `0x5004`, instance 0 during the interval, and report counts,
value, phase and overflow after identity. Record both entry and successful
return only if safely attributable: an entry alone is a request, not proof of
a completed store. Check argument layouts, exact build/UUID, signatures,
branch-range and register/flags preservation before implementation. Use
release/acquire publication for concurrent buffer records and mark window
boundaries explicitly; ordering across CPUs is an observation, not a global
hardware ordering proof. Avoid logging raw pointers and keep full archives
private. A concurrent unrelated writer must not be labeled the cause merely
because it falls in the interval.

A matching completed software store would give a concrete writer and value to
trace. No matching store would only exclude calls passing through the
instrumented method with the chosen filters and hook window; direct MMIO,
aliases, firmware and hardware updates would remain viable. If either sample
or the window markers are missing, or the buffer overflows, the result is
inconclusive. Existing undocumented reads and any new hooks can perturb
scheduling or hang/reboot iPadOS. The probe is a design, not built or run.

Evidence inputs: `research/probes/j81-page5control/j81_page5control_capture.c`,
`research/probes/j81-page5control/j81_page5control_shell.S`,
`artifacts/live/private/gpu-offline/ios15-agx-disasm.txt`, the 19H394 kernel
and both iOS PMGR candidate vtable pointers. Full kernel images and logs remain
private.
