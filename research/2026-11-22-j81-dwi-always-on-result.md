# Point 2 result: dwi always-on from boot (2026-11-22, run 1)

Plan: `2026-11-22-j81-dwi-always-on-plan.md`. Kernel notes a2dda27 (Image identical to the earlier observer kernel), DT `apple,always-on` on ps_dwi, no late dwi store.

- dwi PS 0x20e020120 read 0xff at the FIRST snapshot (S0) and at every later one: Linux no longer switches it off.
- Same recipe as before (PLL1, PLL4, MCC, MiscACG, TVM, single GFX activation, bridges, GPC state 1). GFX VID 0x2300c 0 -> 0x164 after activation.
- Identity: core=0x00070500, id=0x011b0803, hi=0x00000000, core_read_ns=459, crumb=on. Identical to the late-store runs.
- PMIC row 0x0128: 00 00 40 00 -> 64 00 64 00 after the batch, held at +10 s.
- Prediction (identical results) confirmed. One device, one run.

Meaning: the patch (0125) is sufficient to replace the poke; the late store is not needed. Remaining: make it part of the production kernel, then ablations (queue note).
Logs (private): `artifacts/live/private/j81-linux-dwialwayson-results-20261122-run1`.
