# J81 Linux compressed-timing test (prepared, not run)

Follows [the single-activation result](2026-11-21-j81-single-activation-result.md): one GFX activation did not fix the
core-ID read. Remaining untested differences include timing (our stages are seconds apart over USB; stock does them
microseconds apart inside `ApplePMGR::start()`) and mapping attributes (the userspace tools use /dev/mem O_SYNC =
Device-nGnRnE; the older kpoll module used posted `ioremap`).

## What it does

`kernel/gpc-page5-kpoll-compressed/gpc-page5-kpoll.c` (module name and sysfs `gpc_state`/`batch` unchanged, so the wrapper,
supervisor and capture code are reused) runs in ONE irq-off kernel batch: both bridge tables (66 stores from the
embedded plan, sha256 1c7b3839...), GPC +0x10000=0xffff0000, +0=0x40000000, +0x1000=0x11, a 10 us poll loop, one page-5 +4
sample and, if bit 30 is set, the core-ID read 0x201000020. All mappings use `ioremap_np` and are made at module load.
The batch result line keeps the old `mode=immediate` format; the core value and intervals are in the new sysfs file
`core` (`core_valid=1 core=0x... bridge_ns= bridge_to_gpc_ns= poll_to_core_ns= core_read_ns=`), readable only if the
batch survived. If the core read hangs, the watchdog resets the iPad: result "no result" in `compressed-result.txt`
(a hang before the core read, in the bridge or GPC part, would look the same; both worked in earlier runs).

## Artifacts (all gitignored except the source)

- Module: `artifacts/live/gcroot-gpc-page5-kpoll-compressed/gpc-page5-kpoll.ko`, sha256
  `be51efa4006bfeaf076dca4f3c8c14f9a0cf55b34549167ee55cec774007f441` (built 2026-11-21 against the observer kernel dev store).
  Loadability (the `__ioremap_prot` symbol) is only proven when `insmod` runs; a failure there is safe (wrapper exits).
- Bundle: `artifacts/live/private/j81-compressed-bundle-20261121` = single-activation bundle with that module.
- Runner: `artifacts/live/private/j81-linux-compressed-experiment/runner/boot/j81_observer_paired_campaign.py`
  (no bridge stage, no core tool; `summary-prebatch.txt` is written before the batch; kpoll mode `immediate`).
  Offline test `test_j81_observer_compressed_flow.py` passes; `--verify-only --bundle ...` passes.

## Launch (needs a fresh DFU cycle and the user's go-ahead)

Same two boot commands as the single-activation run with this bundle's `Pongo.bin` and `m1n1-linux.bin`, then
`boot/j81_preflight.sh gfx-request-observer` must say GO, then from the runner dir
`python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-compressed-bundle-20261121`.
