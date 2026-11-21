# J81 Linux single-GFX-activation run: core-ID read still hangs

2026-11-21, one shot, boot ID `0e4b8e60-eec5-420a-8be9-19dc52591d9f`. Plan:
[2026-11-21-j81-single-activation-plan.md](2026-11-21-j81-single-activation-plan.md). Bundle
`j81-single-activation-bundle-20261121` (cycle module with one `pm_runtime_get_sync`, no off/on). Logs (private):
`artifacts/live/private/j81-linux-single-activation-results-20261121-run1/`.

## Result

- The hypothesis (the extra GFX off/on cycle in Linux is what the core read depends on) is **ruled out**.
- `gfx-request.log` holds **exactly one** request: `old=00000300 request=0000000f poll=000003ff auto=1 auto_word=100000ff rc=0`
  (the campaign's new guard accepted it). Every earlier Linux run had three requests (0xf, 0xf0, 0xf).
- All PMGR writes, snapshots and checks passed in Apple's order; the bridge plan, the paired GPC batch and the core-ID
  tool's first four reads matched earlier runs: PMGR 0x3ff, MiscACG 1, page 5 0x40000000, GPC state 1, GPC control 0x40000000.
- GPC poll: 11 polls, last store to successful poll about 296-298 us (iPadOS 289 us, earlier Linux 291 us).
- The read of 0x201000020 (`before-gpu-revision`) never returned: the 20 s watchdog reset the iPad, `core-id-result.txt`:
  "no result". Same failure as every previous Linux run.

## Consequence

State before the core read now matches iPadOS on everything we can read, with Linux's activation count also matched.
Remaining differences: timing (our stages are seconds apart, stock microseconds), unmodeled provider side effects, bridge
state retention between the bridge stage and the read, Device-nGnRE vs nGnRnE mapping attributes of the userspace tools.
Next test: the compressed in-kernel sequence (`kernel/gpc-page5-kpoll-compressed`), run on top of this single-activation bundle.
