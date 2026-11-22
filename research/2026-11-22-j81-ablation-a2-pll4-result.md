# Ablation A2 result: PLL4 write omitted, no-core observation (2026-11-22, run 1)

Plan: `2026-11-22-j81-ablation-a2-pll4-plan.md`. dwi always-on (0xff throughout), nocore module, every step of the full recipe except the PLL4 +0x4008 write.

- PLL4 +0x4008 stayed 0x88480348 in all nine snapshots (never written); PLL1 +0x1008 went 0x80480348 -> 0x40480348 as in the full recipe.
- GPC poll ok (raw 0x00000001 after 29 polls, vs 28 in other runs; ~296 us); page-5 first sample 0x40000000.
- GFX VID 0x2300c = 0x164 after activation; PMIC row 0x0128 00 00 40 00 -> 64 00 64 00, held at +10 s. No hang.

Same observation as the comparator. The PLL4 write is not needed for these indicators. The identity read without it is the next boot (j81-gpu driver, skip_pll4). One device, one run.
Logs (private): `artifacts/live/private/j81-linux-ablation-pll4-results-20261122-run1`.
