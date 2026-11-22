# Research packet 6 result: GPU voltage and recipe necessity (2026-11-22)

Source: `builder-mailbox/from-builder/2026-11-22-j81-gpu-voltage-recipe-result/` (RESULT.md, ablation.tsv, perf-states.tsv, POST-ID-HANDOFF.md; checksums verified). Offline analysis; third-party claims, check before relying.

- Voltage: iBoot 12B410 converts code to mV as 600 + floor(3125*code/1000) mV (host test ran the original routine for all 256 codes). 0x64 = 912 mV in Apple's published table (software conversion, not a measurement). GPU buck identification still inferred.
- DVFM: state 1 (start state) = code 0x64, 365 MHz nominal; state 5 same code at 182.5 MHz. Other codes 0x70 (950 mV), 0x7f (996 mV, largest valid captured code). Frequencies are table predictions.
- Necessity: only DWI is shown to matter. No other step is shown dispensable; nothing established about firmware. Proposed ablation order (one omission per fresh boot, no-core first): PLL1, PLL4, TVM, MCC group, bridge tables; retain MiscACG, dwi, single activation, GPC state 1.
- Always-on early: use the DT `apple,always-on` and omit the late dwi store; its old-value guard (0x200) cannot validate an already-on domain (our runner variant already skips the store and requires 0xff). Compare with the late-enable positive control.
- Bounds: no qualified upper limit or slew rate; do not write voltage words directly. The recipe never explicitly writes the GFX VID word; the stock activation does.
- Packet 5 (post-ID bring-up) is still open; POST-ID-HANDOFF.md is an offline starting point (G4G accelerator tables, META boot path, firmware copy) for it.
