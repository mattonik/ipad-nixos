# Ablation A1-identity result: PLL1 write omitted, identity reads (2026-11-22, run 1)

Plan: `2026-11-22-j81-ablation-a1-id-plan.md`. dwi always-on, id module, every step of the full recipe except the PLL1 +0x1008 write.

- PLL1 +0x1008 stayed 0x80480348 (all snapshots).
- core=0x00070500, id=0x011b0803, hi=0x00000000, core_read_ns=500, crumb=on: identical to the full recipe. No hang.
- GPC poll ok (28 polls), page 5 0x40000000, PMIC row 0x0128 -> 64 00 64 00 held at +10 s.

Conclusion: the PLL1 write is NOT needed for the identity reads (one device, one run; firmware start not tested, so it may still matter later).
Next in the queue: A2, omit PLL4 +0x4008 (no-core first).
Logs (private): `artifacts/live/private/j81-linux-ablation-pll1-id-results-20261122-run1`.
