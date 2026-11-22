# Ablation A2-identity result: PLL4 write omitted, identity reads (2026-11-22, run 1)

Plan: `2026-11-22-j81-ablation-a2-id-plan.md`. j81-gpu driver, skip_pll4=1 (module sha256 33461235...), dwi always-on, PLL1 written, PLL4 not. Logs (private): `artifacts/live/private/j81-gpu-a2-pll4-id-20261122-run1`.

- core=0x00070500, id=0x011b0803, hi=0x00000000, GPC 1 after 28 polls, page5 0x40000000, gfx_ps 0x3ff, core_read_ns 834. Identical to the full recipe. No hang.

Conclusion: the PLL4 write is NOT needed for the identity reads (one device, one run; firmware start untested). Together with A1 (PLL1), neither PLL write is needed for the identity read alone. Not yet tested: both omitted together; TVM (A3), MCC group (A4), bridge tables (A5).
