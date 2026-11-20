# J81 Linux single-activation test: prepared, not run (2026-11-21)

Why: the provider-slots agent result (`2026-11-20-j81-provider-slots-review.md`) showed every archived Linux run does GFX on -> off -> on
(requests 0xf, 0xf0, 0xf, from the 2026-11-06 get/put/get cycle module) while the iPadOS observer does ONE activation (0x300 -> 0xf -> 0x3ff).
The 11-06 test excluded the cycle only in isolation, before MiscACG/TVM/MCC/PLL/order were matched. Single activation + full state was never tried.

What was built (nothing run on the iPad):
- `kernel/gpu-pmgr-cycle-single-get/` (gpu-pmgr-cycle.c, Kbuild, build.nix): the cycle module with one `pm_runtime_get_sync` (no put/get); module identity unchanged
  (module gpu_pmgr_cycle, device gpu-pmgr-cycle, attribute cycle_once) so the existing wrappers/campaign accept it. Built on the builder VM against the exact observer kernel
  (nmjby96..., notes a2dda271...). sha256 795a95ce3fac849ba14a3e939e198a9440e52bd593838b0e7d394e5c3c790d57; undefined symbols identical to the original except __pm_runtime_idle (the removed put).
- Bundle `artifacts/live/private/j81-single-activation-bundle-20261121` = observer bundle with that module and two wrappers (bridge, kpoll) carrying the module's new build-id-note hash 0886d82f... (was 8e4e9917..., method verified on the original module).
- Experiment `artifacts/live/private/j81-linux-single-activation-experiment/runner/boot`: the MCC-replay campaign (PLL1, PLL4, MCC bank, MiscACG, voltage check, TVM, then the activation, bridge, GPC, gated core read) plus a new stop: after the activation the dmesg gfx-request log must show exactly one row
  (old=00000300 request=0000000f); otherwise it stops before the bridge plan. Flow test (incl. new "three-gfx-requests" scenario) passes; `--verify-only` passes; SHA256SUMS written.
Boot: same payload as before (Pongo.bin / m1n1-linux.bin unchanged). Launch from the runner dir: `python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-single-activation-bundle-20261121` (logdir `j81-linux-single-activation-results-20261121-run1`).
Expected outcome: single request row, PS 0x3ff, then the same checks; the interesting result is whether the core read returns 0x00070500 or still hangs.
Housekeeping: six 1.7 GB iPadOS capture folders (`j81-ios-pmgr-*`) moved to the NAS `local-private-archive-20261120/` (checksum-verified) to get under the builder's 15 GB free-space limit; builder VM started for the build.
