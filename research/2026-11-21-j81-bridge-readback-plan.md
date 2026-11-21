# J81 Linux bridge read-back (prepared, not run)

Agent follow-up 2 (`2026-11-21-j81-n61-g4p-review.md`): is every J81 bridge word still what we wrote, after the stores and after GPC? Only two words were ever read
back on Linux (`0x201f00018`/`0x201f80018` = 0x80010004, and the first +0x40000 word of selector 9 earlier); no iPadOS read-back exists.

What: `kernel/gpc-page5-kpoll-bridgerb/` = the no-core control module plus a read-back of all 66 plan offsets (33 per bridge) inside the same irq-off batch, twice:
after the 66 stores (rb1) and after the GPC poll and page-5 sample (rb2). Sysfs `bridge` prints `rb1 t0: ...`, `rb1 t1`, `rb2 t0`, `rb2 t1` (33 words each). Core read stays
disabled. The runner (`artifacts/live/private/j81-linux-bridgerb-experiment/runner/boot`) reads it after the batch, writes `bridge-readback.log` and `bridge-compare.txt`
(per phase/table: words equal to the plan, and each differing entry with offset, written and read value) and appends the comparison to `summary.txt`. A differing word
is recorded, not a failure. Offline flow test (including a `bridge-diff` scenario) and `--verify-only` pass.
Risk: 126 reads of previously unread bridge offsets (only the +0x18 words and one +0x40000 word were read before); a hang would be a watchdog reset with no data (supervised, same as every run).
Artifacts: module sha256 `0ed516c13d88330535acb1620a71bbe838d48c6640fd64206a0fdbba65d63b81`, bundle `artifacts/live/private/j81-bridgerb-bundle-20261121`.
Reading: all equal in rb1 and rb2 -> retention is not the difference (on Linux; iPadOS side still unsampled); differences in rb2 only -> something rewrites/clears bridge words during GPC; in both -> some
words are write-only or masked (compare against the iPadOS readback later).
Launch (fresh DFU, user's go): same two boot commands with this bundle, preflight GO, then from the runner dir
`python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-bridgerb-bundle-20261121`.
