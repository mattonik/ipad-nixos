# Ablation A2: omit the PLL4 (+0x4008) write, no-core first (2026-11-22)

Queue: `2026-11-22-j81-ablation-queue.md`; A1 (PLL1) passed both no-core and identity (46ace51, f508e68). Comparator: the always-on full recipe (32100bb).
Run: NO-CORE control module, dwi always-on, every step except the PLL4 write; +0x4008 must stay 0x88480348 (the runner expects it unchanged); PLL1 +0x1008 IS written as in the full recipe. Bundle `j81-ablation-nocore-bundle-20261122`, runner `j81-linux-ablation-pll4-experiment`.
Pass criteria: GPC poll ok, page 5 = 0x40000000, PMIC 0x0128 -> 64 00 64 00. Then, on a separate boot, the identity run with the j81-gpu driver and skip_pll4.
Prediction: unknown; packet 6 says PLL4 has no shown direct GFX selection, so it may pass like PLL1; PLL4 could still feed a clock the GPC state machine needs.
