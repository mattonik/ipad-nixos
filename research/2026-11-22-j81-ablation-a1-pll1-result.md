# Ablation A1 result: PLL1 write omitted, no-core observation (2026-11-22, run 1)

Plan: `2026-11-22-j81-ablation-a1-pll1-plan.md`. dwi always-on (0xff at S0 and after), nocore module, every step of the full recipe except the PLL1 +0x1008 write.

- PLL1 +0x1008 stayed at the Linux value 0x80480348 in every later snapshot (A, C, D10); PLL4 +0x4008 = 0x48480348 as in the full recipe.
- GPC poll ok (raw 0x00000001 after 28 polls, ~287 us); first page-5 sample 0x40000000 (bit 30 set).
- GFX VID 0x2300c = 0x164 after activation; PMIC row 0x0128 00 00 40 00 -> 64 00 64 00, held at +10 s.
- Same observation as the full-recipe comparator at every checked point. No hang.

So the PLL1 write is not needed for these indicators (poll, page 5, PMIC). That does NOT yet show the identity read passes without it: that needs the identity module on a separate boot (next: A1-identity, then A2 PLL4). One device, one run.
Logs (private): `artifacts/live/private/j81-linux-ablation-pll1-results-20261122-run1`.
