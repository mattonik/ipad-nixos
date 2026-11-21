# J81 compressed-timing run 1: harness failure, NOT a hardware result

2026-11-21, boot ID `6cb2365c-6992-4015-b7cc-7fc25c55a18f`, logs (private)
`artifacts/live/private/j81-linux-compressed-results-20261121-run1/`.

The PMGR writes, the single GFX activation (`gfx-request.log`: one request, `old=00000300 request=0000000f`) and snapshot A
all passed. Then `kpoll.log` stops right after `stage=watchdog-armed timeout=20`: the wrapper printed nothing, not even its
first checkpoint (`stage=before-pmgr-read`). The supervisor fails closed when its child exits, so the armed 20 s watchdog
reset the iPad. `compressed-result.txt`: "no result".

## Cause

`gpu-gpc-page5-kpoll-run-observer` (inherited from the single-activation bundle) contains
`case "$mode" in paired) ;; *) exit 2 ;; esac`. The compressed module's capture passes mode `immediate`, so the wrapper exited 2
before any checkpoint, and the compressed batch **never ran**. The module was never loaded; nothing was learned about the
core read. The run consumed one boot and one DFU cycle.

## Fixes (committed state of the bundle is private; the logic is described here)

- Bundle wrapper now accepts `immediate` only (sha256 `6ce82fde44cca68ce824a71871a592f92c167fbb70ed82a2676b2c8d68f10ffc`).
- The campaign now dry-runs the wrapper with `</dev/null` BEFORE arming the watchdog: it must print `stage=before-pmgr-read`
  and leave no state (`/tmp/gpu-gpc-page5-kpoll.once`, loaded module). A rejected argument now stops the campaign safely
  instead of resetting the iPad. New offline test scenario `wrapper-rejects`; the flow test and `--verify-only` pass.
- Lesson: a wrapper change that touches argument handling needs the dry run; "capture parser accepts immediate" is not enough.
