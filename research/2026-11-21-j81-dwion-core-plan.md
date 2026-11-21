# J81 DWI-on + core read with breadcrumbs: plan (2026-11-21)

Follow-up to research/2026-11-21-j81-dwion-result.md: with DWI on, PMIC row 0x0128 follows
the GFX request to 64/64 and the no-core batch returns. This run adds the core read.

Recipe: identical to the DWI-on run (PMGR writes in Apple's order, one guarded DWI-on
store, post-DWI snapshot, one GFX activation, compressed batch), but with the
crumbs-core module (sha256 d9398f84..., core read ENABLED, framebuffer squares) from
bundle j81-crumbs-core-bundle-20261121 (Pongo.bin/m1n1-linux.bin identical to all bundles).

Runner (private): artifacts/live/private/j81-linux-dwioncore-experiment/runner/boot,
a copy of the DWI-on runner with only: module pin 4827876e -> d9398f84, core-attribute
regex accepting the crumb=on|off suffix, summary text. Offline flow test passes;
--verify-only passes against the crumbs-core bundle; SHA256SUMS 271 entries.

Expected: if the rail was the cause the core read returns (0x00070500 on iPadOS) and the
batch survives; if it still hangs the watchdog resets the iPad and the framebuffer shows
squares 1-5 (the sixth means the batch finished). A hang leaves no PMIC after-batch
sample; the before-batch row and the DWI snapshot are logged before it.
One shot per boot; fresh DFU boot required.
