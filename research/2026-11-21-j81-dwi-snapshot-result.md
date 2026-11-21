# J81 Linux DWI power state and PMIC rows on the no-core control: DWI is OFF, the GFX rail request never reaches the PMIC

2026-11-21, one shot, logs (private) `artifacts/live/private/j81-linux-dwi-results-20261121-run1/`. Plan: [2026-11-21-j81-dwi-snapshot-plan.md](2026-11-21-j81-dwi-snapshot-plan.md).
Campaign: no-core control (module `4827876e...`), single GFX activation, both gates passed, exit 0, iPad still up. New tool `pmu-peek` (static, read-only combined I2C read of bus 0, address 0x3c; sha256
`c903be7ce3e5b02834ca9444d6f193d6ccf8e23880c83cdafb67a956f0536977`, source `tools/pmu-peek/`) because the observer userland has no i2c-tools.

## Result
| Quantity | S0 | S5 | A (after activation) | C (after batch) | D10 (10 s later) |
|---|---|---|---|---|---|
| DWI PS `0x20e020120` | 0x200 | 0x200 | 0x200 | 0x200 | 0x200 |
| GFX VID `0x20e02300c` | 0 | - | 0 | 0x164 | 0x164 |
Batch: GPC state 1 after 28 polls, ~286 us, page 5 = 0x40000000. PMIC rows (identical before the batch, right after it and 10 s later):
`0x0100: 88 00 88 00 10 e0 00 21` (CPU rail), `0x0128: 00 00 40 00 40 e0 0f 31` (buck 1, candidate GPU rail), `0x0150: 70 00 70 00 40 ff 0f 21`, `0x01c8: 70 00 70 00 40 e0 0f 21`.

## Reading
- DWI's power state is 0x200 = **off** for the whole run, on the observer boot that has MiscACG, page 5 high and the full PMGR sequence. The internal GFX voltage request does fire (0x2300c 0 -> 0x164 after the
  GPC request), but the PMIC's buck 1 stays at code `0x00` with actual `0x40`, before and after, exactly as on the Nov 11 boots with DWI off (`2026-11-11-j81-dwi-voltage-transport.md`):
  **the GFX rail request does not reach the PMIC.** The GPU core may be unpowered, or at its default (800 mV minimum) voltage, when the core load runs.
- iPadOS keeps `dwi` on (LLB keeps it; Linux switches it off about 0.7 s into boot together with 19 other boot-chain domains), so on stock the same request would reach the PMIC. This is the first measured Linux/iPadOS difference
  at the point of the core read that is not a matching register.
- Caveat (agent, `2026-11-21-j81-hidden-state-review.md`): even bytes 64/64 would not prove power-good, ramp or isolation; a code on buck 1 is circumstantial for "buck 1 is the GPU rail" (inference from the min/max pattern).
- The Nov 14 "DWI ruled out" tests predate MiscACG (Nov 19), so they could not discriminate; with page 5 high this is the first valid look.

Next test: switch `dwi` on (`boot/pmgr-dwi-on.c`: PS 0x20e020120 0x200 -> 0xff, one acknowledged write) BEFORE the GFX activation, repeat the no-core control and read the PMIC rows again (expect buck 1 `64 .. 64` if the request now reaches it);
if so, run the core-read variant on the same recipe.
