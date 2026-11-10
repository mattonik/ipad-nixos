# J81 iOS paired page-5 probe

This iPadOS 15.8.5 (19H394) probe compares `0x20e005004` twice on the same boot: immediately after the first GFX provider return and after the identity reads. The existing PMGR read method is called with region 0, offset `0x5004`, instance 0. A saved PMGR object and enabled interrupts are required; missing markers are inconclusive. The object's lifetime and physical address correspondence are inferred. The extra undocumented reads can have side effects, hang or reboot the device, and early logs may be lost.

`PAGE5-early-before` followed by `Q=` identifies the early value; `PAGE5-before` followed by `Q=` identifies the late value. Even a difference does not establish which thread or operation changed the bit, or whether it affects GPU accessibility. The probe performs no page-5 writes.

The private module `artifacts/live/private/j81-ios-page5pair-probe/page5-pair4` has SHA-256 `673df874ec641cc3f175bb92626cfa70de3631c13285f24e7b6365062f7691d8`. The Pongo checkout and build follow the [early probe](../j81-page5early/README.md), registering `j81_page5pair_capture` with `KPF_CFLAGS=-DJ81_PAGE5PAIR_DEVICE_BUILD`.

The host KPF harness accepted the target kernel and rejected each of nine missing or duplicated signatures and a wrong UUID. A native ARM64 simulation verified fixed read arguments, early/late order and late one-shot behavior. These checks do not establish hardware safety or object lifetime. The linked binary includes unused assembly from other experimental probes; only the paired component is registered.

The hardware run completed: early `Q=00000000`, late `Q=40000000`, followed
by successful firmware boot. See the [capture result](../../2026-11-10-j81-page5-capture-results.md#paired-ios-4-timing-on-one-boot).
