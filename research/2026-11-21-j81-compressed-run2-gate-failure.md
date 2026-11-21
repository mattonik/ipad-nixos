# J81 compressed-timing run 2: stopped by my own gate, NOT a hardware result

2026-11-21, boot ID `bcfeebde-c52d-416f-9059-f31c6c1dc350`, logs (private) `.../j81-linux-compressed-results-20261121-run2/`.
Everything up to the gate passed (PMGR writes, single GFX activation: one request, snapshot A). The new wrapper dry run
passed (`stage=before-pmgr-read`, `rc=1`). The second gate check then compared the console output to exactly `CLEAN`, but
the real console appends its prompt (`CLEAN/ #`), so the campaign stopped with "wrapper dry run left state behind" before
the watchdog was armed. Read-only inspection afterwards: no `.once` guard, no module loaded, same boot, `runtime_usage` 1.
The compressed batch never ran.

Cause: my gate compared output exactly, and my test mock returned a bare `CLEAN` instead of the console's `CLEAN/ #`.
Fix: prefix match; mock now returns `CLEAN/ #`. The boot cannot be reused (PMGR writes and activation already done), so the
next attempt needs a fresh DFU cycle. Lesson: test mocks must reproduce the console's prompt suffix.
