# Ablation A2-identity: PLL4 write omitted, identity reads via the j81-gpu driver (2026-11-22)

After A2 no-core (c53dd2e). j81-gpu module with `skip_pll4=1` (sha256 recorded in the run plan.txt); PLL1 is written, PLL4 is not (+0x4008 stays 0x88480348), all other steps as the full recipe, then identity reads (core, id, hi). No survey reads. Dashboard stopped.
Comparator: core 0x00070500, id 0x011b0803, hi 0, GPC 1 after ~28 polls, page5 0x40000000.
Prediction: unknown; the no-core observation matched, so likely the same. A hang would mean PLL4 is needed for the identity read (watchdog reset, fresh DFU).
