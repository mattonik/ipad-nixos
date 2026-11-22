# J81 GPU identity read: result (2026-11-22, run 1)

Plan and prediction: `2026-11-22-j81-gpu-identity-plan.md` (committed before the run).

Same recipe as the two core-read runs (dwi on, single GFX activation, compressed
in-kernel batch), plus two extra reads after the core read. Module sha256 83263730...

| register (0x201000000 +) | value | note |
|---|---|---|
| +0x20 | 0x00070500 | B=7, V=5 (same as runs 1 and 2) |
| +0x18 | 0x011b0803 | low 16 bits 0x0803 = N=8, C=3 |
| +0x24 | 0x00000000 | read is safe, value zero |

- Prediction was CORE_ID low 16 bits 0x0803: **confirmed**. Together with B=7, V=5 this
  is BVNC 7.5.8.3, the offline "G4G A1" entry (packed 0x07050803).
- The upper half of +0x18 (0x011b) was not predicted; meaning unknown (possibly a
  config/ID field). Not interpreted further.
- No hang: crumb squares reached 8 path (crumb=on), core_read_ns=709.
- PMIC row 0x0128 went 00 00 40 00 -> 64 00 64 00 and held 10 s, as before.
- One device, one run. Reads only; the three registers are now known safe on this recipe.

Logs (private, not in git): `artifacts/live/private/j81-linux-dwioncore-id-results-20261122-run1`.

Next: point 2 (dwi always-on in the real boot, patch 0125), then narrow the recipe.
