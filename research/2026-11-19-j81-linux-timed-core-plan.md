# J81 Linux timed core-ID test after the MiscACG write: plan (2026-11-19)

Why: with MiscACG = 1, page-5 bit 30 rises on Linux, but the core-ID read hung when done seconds after the paired GPC batch ([result](2026-11-19-j81-linux-core-id-result.md)).
iPadOS reads it about 30-60 us after the GPC poll succeeds (page 5 sampled first). This test removes the delay.

Change versus the core-ID campaign (diff `2026-11-19-j81-linux-timed-core-campaign.diff`): the paired kpoll batch is replaced by one watchdog-supervised tool, `boot/gpu-gpc-timed-core.c`
(freestanding static aarch64, Homebrew LLVM 14 clang+lld, runs via the pinned supervisor's `--core-revision-cycle` mode and wrapper `boot/gpu-gpc-timed-core-run.sh`):
- host-acknowledged read gates: GFX PS == 0x3ff, MiscACG == 1, GPC state == 0; any failure prints `stage=skipped` and finishes cleanly (no GPC write, no core access);
- then one host-acknowledged stage covers the whole sequence with no host round trips: GPC writes (+0x10000 <- 0xffff0000, +0 <- 0x40000000, +0x1000 <- 0x11, the same stores as the observer's kpoll module and iPadOS),
  poll +0x1000 until (raw & 0x1f) == 1 (cap 4000 reads), read counter, read page 5 +4; if bit 30 is clear: skip (no core access); else read the core ID at 0x201000020 immediately; report the poll count and the 24 MHz tick count from poll success to the read;
- the only writes are the three GPC stores; the PMGR/core/page-5 mappings are read-only. A hung core read triggers the supervisor's 20 s hardware watchdog (device reset); a partial summary is on disk first.
After a successful step a snapshot C of the seven PMGR words is taken. No paired kpoll sample this time (page 5 is read once inside the tool).
Offline tests: `boot/test_j81_observer_timed_core_flow.py` (full read -> 0x00070500, gate skip, reordered checkpoint -> no feed, hang -> no result and no summary).
Untested on device: the tool binary itself.
Reading the result: a plausible core ID (iPadOS 0x00070500) means the core window responds only shortly after GPC completion; a hang again means timing is not the (only) missing piece.
