# Ablation A1-identity: PLL1 write omitted, identity reads (2026-11-22)

After A1 no-core (46ace51). Same as the always-on identity run (32100bb) except the PLL1 +0x1008 write is omitted (word must stay 0x80480348). Bundle `j81-dwialwayson-bundle-20261122` (id module), runner `j81-linux-ablation-pll1-id-experiment`.
Comparator values: core 0x00070500, id 0x011b0803, hi 0, PMIC 0x0128 -> 64 00 64 00.
Prediction: unknown; the no-core observation matched, so the read may pass; PLL1 could still matter for the core fabric clock. A hang would mean PLL1 IS needed for the identity read (squares show the step if the dashboard does not repaint; dashboard still running here).
