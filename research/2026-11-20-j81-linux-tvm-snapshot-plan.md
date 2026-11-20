# Linux +0x2d000 snapshot run: plan (prepared 2026-11-20, not run)

Purpose: the SoC TVM control (PMGR +0x2d000, region 0, group 3, rail 1, stock request old|1, no poll) has no retained sample on a page-5-high boot or on the working iPadOS boot (`research/2026-11-20-j81-archive-only-results.md`). This run records it. Observation only: no TVM write, no core-ID access.

Change vs the MiscACG-write campaign (diff: `2026-11-20-j81-linux-tvm-snapshot-campaign.diff`): the PMGR word snapshot gets one more word, `2d000` (8 words, READY `words=8`). Snapshots A, B, B2, C all carry it, so it is sampled before the GPC request (B2, after the guarded MiscACG store) and after page 5 rises (C). Summary adds a `tvm 0x2d000 A= B= B2= C=` line. Everything else is unchanged: cycle, bridge plan, guarded MiscACG store (one, only if it reads 0), paired GPC/page-5 batch, one shot per boot, a failure stops and is not retried on that boot. +0x2d100 is not read. The +0x2d000 read was already done safely on Linux (2026-11-11).

Tests: `test_j81_observer_paired_campaign.py` and `test_j81_observer_miscacg_write_flow.py` pass (8-word snapshots); `--verify-only` against bundle j81-observer-paired-20261119-v1 passes; writer sha256 846d9e86.... (The unmodified `test_j81_observer_paired_flow.py` fails at writer staging, as it did before this change, because it models the no-write flow.)

Prediction: if the missing-enable hypothesis holds, C stays 0x00000000 on page-5-high Linux while the iPadOS counterpart reads nonzero (bit 0 set). Linux 0 alone does not decide it; the working iPadOS readback at the same phase is still needed.

Boot: DFU, palera1n Pongo shell with the bundle Pongo.bin, load_m1n1.py with the bundle m1n1-linux.bin, `boot/j81_preflight.sh gfx-request-observer` = GO, then from `artifacts/live/private/j81-linux-tvm-snapshot-experiment/runner/boot`: `python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-observer-paired-20261119-v1`. Artifacts: `artifacts/live/private/j81-linux-tvm-snapshot-experiment/` (git-ignored).
