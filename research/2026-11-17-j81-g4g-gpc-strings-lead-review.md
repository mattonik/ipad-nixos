# J81 G4G "setGPCPerformanceState / stuck" lead: already covered, no new step

Date: 2026-11-17. Offline review of existing notes only; no binary was
re-opened, no device touched.

## Question

The G4G binary names Fender/GPC bring-up (`AGXFenderCommon::setGPCPerformanceState`,
"GPC state transition is stuck"). Does tracing it reveal a register write or
poll before the RGX core-ID read (`0x201000020`) that explains PMGR page-5
`0x20e005004` bit 30 staying clear on Linux and bare PongoOS?

## Answer

No new step. What those strings correspond to is already traced:

- `setGPCPerformanceState` (15.8.8 `0xfffffff006698d94`): read `GPC+0x1000`,
  wait bit 4 clear, write `state | 0x10`, read back, store request.
  The "stuck" string is that wait's timeout path. See
  `2026-11-09-j81-gpc-state-vs-gfx-perf-selector.md`.
- The pre-ID path (8.1 `0xffffff80032935a0`, 15.x equivalent) is:
  provider clock `+0x568(1,0)`, provider power `+0x570(1,&out,0)`,
  `GPC+0x10000 = 0xffff0000`, `GPC+0 = 0x40000000`, `GPC+0x1000 = 0x11`,
  optional bit-4 poll, `IODelay(10)`, then RGX `+0x20`, `+0x18`. No hold/reset
  routine sits between (`2026-11-09-j81-pre-id-readiness-sequence-audit.md`).
  Linux test4 and the PongoOS split already replay exactly this.
- On a live iPadOS 15.8.5 boot, page-5 `+4` is 0 after the provider
  clock/power calls and after the `GPC+0 = 0x40000000` store, and becomes
  `0x40000000` after the stock `0x11` request and poll
  (`2026-11-16-j81-agx-postpower-page5-result.md`). So the GPC request
  is the *trigger* in both OSes; it is not the missing step.
- The Fender state setter does not select a PMGR GFX table entry, and no call
  edge puts the separate firmware-hold routine (`329eb28`) before the ID read.

## What this implies

The write sequence inside G4G is fully known and matches what Linux does. The
difference must be state that exists when the GPC request is issued, not an
extra G4G register write. The KPF probe at the end of `ApplePMGR::start`
(2026-11-14) showed the same Linux recipe working there, so the missing item is
established during XNU boot up to that point.

The best-supported open candidate remains the one from the DWI review:
pre-OS the PMGR voltage manager is disabled (`0x20e023000 = 0xf01`;
`1` after `ApplePMGR::start`). The PongoOS split failed with it still
disabled, so it does not prove m1n1/Linux harmless. Suggested next test (needs
Martin's go-ahead and his own probe build): from the Pongo state, perform the
iPadOS-style volman enable (seed CPU/SRAM codes at `0x23010`/`0x23004`, clear
`0x23000` bits 11:8), then the unchanged GPC recipe, and read page-5 `+4`.
Success means bit 30 depends on volman; failure sends the bisection to the
`ApplePMGR::start` entry hook.

## Not done

I did not re-decompile 15.8.8 for other callers of the setter; the sources
above already show one binding. Further static work on these strings is
unlikely to add a register.
