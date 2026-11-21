# J81 GPU bring-up step 1: read the rest of the identity registers (2026-11-22, plan)

Context: with the PMGR dwi domain on, the core read at 0x201000020 returned 0x00070500 twice
(research/2026-11-21-j81-dwi-gpu-core-id-summary.md). Read as CORE_REVISION: B=7, V=5, which
matches the "G4G A1" match entry (branch/version 7,5, packed 0x07050803) found offline in the
12B410 kernelcache (research/2026-11-04-j81-gpu-offline-trace.md).

Prediction (written before the run): CORE_ID at +0x18 has low 16 bits 0x0803 (N=8, C=3), i.e. packed
BVNC 7.5.8.3. +0x24 is the high word if the 64-bit packed layout is used; unknown, no prediction.

Recipe: identical to the DWI-on core run, with module kernel/gpc-page5-kpoll-id (sha256 83263730...)
which after the +0x20 read also reads +0x18, then +0x24 (32-bit each, same irq-off batch,
non-posted mapping already covering the page). Framebuffer squares: 6 before +0x18, 7 before +0x24,
8 after the batch; on a hang the number of squares is the last step reached. Runner (private):
j81-linux-dwioncore-id-experiment, bundle j81-id-bundle-20261121; offline flow test passes,
--verify-only passes. One shot per boot, fresh DFU boot.

Risk: reads only, same rail state as the two successful runs; the reads of +0x18/+0x24 are not
individually proven safe. A hang resets the iPad via the watchdog.
