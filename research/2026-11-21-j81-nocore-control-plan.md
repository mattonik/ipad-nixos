# J81 Linux core-read-off control (prepared, not run)

Why: compressed run 3 (`2026-11-21-j81-compressed-run3-result.md`) hung inside the in-kernel batch, but a hang cannot be located. The agent's
top-ranked follow-up (`2026-11-21-j81-n61-g4p-review.md`) is the same batch with the core load removed.

What: `kernel/gpc-page5-kpoll-nocore/` = the compressed module with `#define CORE_READ 0`; identical otherwise (same five `ioremap_np` mappings incl.
the unused core mapping, same 66 bridge stores, GPC request, poll and page-5 sample, all irq-off). The batch returns the normal result line
(GPC raw, polls, timestamps, page-5 +4 value) and `core` reports `core_valid=0 reason=core-read-disabled`.
Artifacts: module `artifacts/live/gcroot-gpc-page5-kpoll-nocore/gpc-page5-kpoll.ko` sha256
`4827876e30d369a36cf361e0281d2b52e07e1a2e046b40c6faf1df2ce06c6045`; bundle `artifacts/live/private/j81-nocore-bundle-20261121` (compressed bundle with this module,
fixed wrapper); runner `artifacts/live/private/j81-linux-nocore-experiment/runner/boot` (compressed runner with the same dry-run gates; flow test passes,
`--verify-only` passes).

Reading the outcome:
- Batch returns normally -> the run-3 stall was the core read itself; compressed timing and non-posted mappings are not the cause.
- Batch hangs -> the stall is in the in-kernel bridge/GPC/page-5 part (never run in this form before); then shorten at stage boundaries.

Launch (fresh DFU cycle, user's go-ahead): same two boot commands with this bundle's `Pongo.bin`/`m1n1-linux.bin`, preflight GO, then from the runner dir
`python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-nocore-bundle-20261121`.
