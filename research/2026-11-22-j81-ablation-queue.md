# Queue: recipe ablation runs (2026-11-22)

Runs after the point-2 check (dwi always-on from boot, no late dwi store, identity read repeats). Basis: packet 6 `ablation.tsv`.

Rules for every run: fresh boot, the full working recipe as comparator, omit exactly ONE operation, dwi on (always-on), single GFX activation, same mappings, 20 s watchdog and crumbs, dashboard stopped before the batch so squares survive a hang. Start with a no-core observation, record last stage, actual PLL/bank/MiscACG/TVM/dwi words, PS, bridge sequence, GPC raw, page 5, PMIC row before/after. Do not go to the identity reads if a precursor is unexpected. Repeat any difference with the control. Combine omissions only after each passes alone. One shot per boot; each needs the preflight GO and the user's explicit go. Commit each result at once.

Order: 0 point-2 positive control (always-on, no store) -> A1 omit PLL1 +0x1008 -> A2 omit PLL4 +0x4008 -> A3 omit SoC TVM 0x2d000 -> A4 omit the five MCC bank writes as a group -> A5 omit bridge tables (read inherited values first; stop at the no-core result) -> combinations of the passing omissions.
Retained throughout: MiscACG, dwi on, single activation, GPC state-1 request and poll.

Status: not started. Blocked on the point-2 payload (build running, check kernel notes sha a2dda27).
