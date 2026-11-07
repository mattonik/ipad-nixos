# J81 DISP0 PS86 Linux observation boundary

Offline cross-check of the Nov. 7 read-only control-boot snapshot and the
pinned Linux PMGR driver. No device action or MMIO read was performed.

The iOS 8.1 `device-clocks` record ID 28 (`DISP0`) names PMGR power-state
index 86. The state-word offset is `0x20000 + 8 * 86 = 0x202b0`; with the
J81 PMGR base at `0x20e000000`, its physical address is `0x20e0202b0`.
The live runtime FDT and sysfs inventory expose the corresponding Linux node
`/soc/power-management@20e000000/power-controller@202b0`, compatible with
`apple,t7000-pmgr-pwrstate`, and platform device
`20e000000.power-management:power-controller@202b0`, bound to
`apple-pmgr-pwrstate`. Its `power/runtime_status` is `unsupported` and
`runtime_usage` is `0`; these are Linux runtime-PM attributes, not a readback
of the PMGR word.

The pinned `pmgr-pwrstate.c` maps each node's `reg` into its parent's PMGR
regmap and registers a generic power domain plus reset controller. It has no
per-register raw-read sysfs attribute. The current boot did not mount debugfs,
so `pm_genpd_summary`, clock, or reset debug views are unavailable. The
read-only inventory shows the inherited `simple-framebuffer`/`simpledrmdrmfb`
at 1536x2048; it does not instantiate a Linux DCP/KMS driver. Apple-specific
`device-clocks` processing, the DISP0 software mode (`+0x980`), and the GFX
busy/MCC callback state are absent from this Linux provider.

No provider sysfs attribute exposes the raw word. The existing read-only
`uartpeek pmgr` command already maps the PMGR page and reads PS indices
`0x50..0x59`, including word `0x20e0202b0` (PS index `0x56`). Its recorded
Oct. 11 result was `0x1f0002ff`; this is a prior-boot sample, not the
Nov. 7 snapshot. The separate `gpu-pmgr-peek` helper is acknowledgement-gated
but hard-codes only GFX at `0x20e020320`. A fresh read of PS86 could establish
only the raw target/actual/auto/reset word at that instant. The old tool label
mistook the state index for a UART device ID; the iOS record table maps PS86
to DISP0 and UART6 to PS58. Neither read tells whether Apple's DISP0 mode or the
conditional display/cache callbacks ran, so no new probe is justified for
those unresolved questions.

Evidence: `research/2026-11-07-j81-core-read-missing-apple-dispatch.md`
(record distinction and unknown state),
`research/2026-11-07-j81-soc-busy-display-action-before-rgx.md`
(conditional `+0x980`/callback path),
`artifacts/live/j81-readonly-20261107T114456Z/{fdt_display_controller,sysfs_display_controller,display_classes}.txt`,
`artifacts/live/private/gpu-offline/linux-src/drivers/pmdomain/apple/pmgr-pwrstate.c`,
`research/2026-11-05-j81-clock-reset-inventory.md` (debugfs unavailable), and
`boot/uartpeek.c` plus `research/2026-10-11-uart3-register-capture.md` (the
existing read-only gate-window capture).
