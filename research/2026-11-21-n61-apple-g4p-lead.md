# N61 (iPhone 6, A8/T7000) `apple-g4p` driver and OrchardLinux issue 61: a possible lead for the J81 core-ID hang

2026-11-21. Sources given by Martin; external content, **unverified, different SoC** (T7000 A8, not T7001 A8X). Pinned copy of everything below:
`artifacts/live/private/n61-g4p-e074df5/` (private, gitignored) and the research-agent packet `to-builder/2026-11-21-j81-research-n61-g4p/`.

- Driver: <https://github.com/jeroentrappers/linux/tree/n61/drivers/gpu/drm/apple-g4p> (branch `n61`, pinned to commit
  `e074df51e54d17cc85404b1efba24dcd5f4573e5` of 2026-11-21 11:07Z, "drm/apple-g4p: C7 probes for the USC store path"). Files:
  Kconfig, Makefile, `g4p.h`, `g4p_boot.c` (45 KB), `g4p_drv.c`, `g4p_fw.c`, `g4p_fw.h`, `g4p_fwinit.c`, `g4p_mmu.c`. Licence line:
  `GPL-2.0-only OR MIT`. DT: `arch/arm64/boot/dts/apple/t7000.dtsi` (`gpu@201000000`, `apple,t7000-g4p`), `t7000-n61.dts`.
- Comment: <https://github.com/OrchardLinux/orchard/issues/61#issuecomment-7060785458> by `amethyst-oak`, 2026-11-21 09:45Z.
  Claims for the iPhone 6: "RGX registers answer once PMGR MiscACG (0x20e032000 bit 0) is set. iBoot clears it and XNU's enableACG sets
  it; this was the 'first GPU register read hangs' problem"; Apple META firmware boots, commands complete (stamp, event, IRQ), an empty
  compute job completes, a 1x1x1 compute kernel writes memory. The thread is otherwise a user asking to be told when it works.

## What the driver does at power-up (`g4p_power_on_locked`, `g4p_drv.c`), from the source
1. `pm_runtime_resume_and_get` = ps_gfx through genpd (target 0xf, wait for actual).
2. **MiscACG bit 0 set AFTER ps_gfx** (read-modify-write at 0x20e032000), only if the range is present; RGX access is refused otherwise.
3. Bridges: bridge 10 gets ONE pair `0x18 = 0x80010004`; bridge 11 gets 32 words `0x007c7c01 ...` at **offsets 0x00..0x7c** (DT
   `apple,bridge10-settings`, `apple,bridge11-settings`; bridge windows 0x201f00000 and 0x201f80000, 0x1000 each).
4. "Fender wake" (Fender at 0x201e00000, our "GPC"): +0x10000 = 0xffff0000, +0 = 0x40000000, +0x1000 = 0x11 and poll bit 4, udelay(10).
5. `CORE_REVISION` (+0x20) then `CORE_ID` (+0x18), 32-bit reads straight after the wake, "as AGX readChipInfo".
It does NOT write the PLL +8 words, the MCC bank, the SoC TVM word or the voltage manager, which our Linux runs replay.

## Where it differs from our Linux sequence (what to check, NOT conclusions)
| | N61 driver | our J81 Linux runs |
|---|---|---|
| MiscACG vs GFX power-on | after ps_gfx | before (Apple's order, 19H394) |
| bridge 10 (0x201f00000) | one write: +0x18 | 33 pairs: +0x18 and 32 words at **+0x40000..0x4007c** |
| bridge 11 (0x201f80000) | 32 words at **+0x00..0x7c** | the same 33 pairs as bridge 10 (tables identical, offsets +0x40000) |
| PLL/MCC/TVM/vm_sram | not touched | replayed |
| ps_gfx activations | one | one (single-activation run) / three before |
Our plan (`research/2026-11-10-j81-ios-corrected-bridge-result.md`) came from the J81 ADT: both tables start `0x18=0x80010004` then
32 pairs at 0x40000..0x4007c. The N61 DT writes the same 32 values to bridge 11 at offset 0, not at +0x40000. If the N61 layout is the
right reading of what `ApplePMGR::_configureBridge` does, **our Linux bridge stores may not configure the real bridge-11 registers**;
iPadOS probes would not show it, because stock had already configured the bridges before our hook ran its Linux-style replay.
This is the most testable difference and has not been examined on J81. Whether T7001's layout equals T7000's is unknown.

## Caveats
- The issue comment is a claim by a third party; the source shows what their driver does, not that it works on every boot.
- T7000 (GX6450) vs T7001 (GXA6850): bridge layout, register map and ADT may differ.
- The driver cites a private bring-up repo (`re/GPU-BRINGUP.md` 8.11/8.12/8.19/8.20, `re/GPU-DRIVER.md`) that we could not fetch
  (`jeroentrappers/linux-on-iphone6` is 404 under that name); the research agent was asked to say what else is needed.

Next: research request `2026-11-21-j81-research-n61-g4p`, results to `from-builder/2026-11-21-j81-n61-g4p-result/`.
