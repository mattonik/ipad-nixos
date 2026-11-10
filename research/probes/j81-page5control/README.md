# J81 iOS GPC control boundary probe

Experimental 19H394 probe extending [the power-boundary capture](../j81-page5power/README.md). It adds a page-5 read after the GPC control write and before the `0x11` state request. It has five potential samples: early `Q`, post-provider `T`, post-control `C`, post-poll `M`, and post-identity `Q`. The `C`, `T` and `M` values are buffered and printed at identity in that **logging order**, not sample order. A missing marker is inconclusive.

The added hook replaces the original `mov w8,#0x11`, saves general registers and NZCV with a 320-byte frame, checks thread, PMGR object, IRQ state and exact known PMGR reader target, performs a single read, restores state and executes the original instruction. It uses no SIMD in this added hook; pre-existing hooks still use SIMD. It cannot prove that the preceding GPC store completed or persisted, that the runtime mapping matches the Pongo ADT, or that changing the number and timing of reads has no effect.

Private module `artifacts/live/private/j81-ios-page5control-probe/page5-control4`, SHA-256 `bbcbae242a2e254d1b7f12bd9764d07f03b8055b38863ca8c754711b00b26ca6`; same Pongo environment as the prior probes, component `j81_page5control_capture`, build flag `KPF_CFLAGS=-DJ81_PAGE5CONTROL_DEVICE_BUILD`.

The exact 19H394 kernel passed the positive KPF check. Eleven independently missing or duplicate signatures and a wrong UUID were rejected. Host ARM64 simulations tested five reads, expected logging order, the restored `0x11` instruction, one-shot behavior, wrong thread and method targets, GPC busy path, and IRQ-masked skip. They do not establish real kernel register state, runtime locks, object lifetime, stack headroom, physical mapping or MMIO side effects. Additional undocumented reads can perturb timing, stall or reboot; if an early read stalls, buffered logs may be lost. No device run has been performed.

The hardware run reported early `0`, post-provider `T=0`, post-control `C=0`,
post-poll `M=0x40000000`, and late `0x40000000`, followed by firmware startup.
See the [capture result](../../2026-11-10-j81-page5-capture-results.md#gpc-control-boundary-transition-after-control-sample).
