# J81 Linux single-variable MiscACG write: plan (2026-11-19)

Basis: [iPadOS reads MiscACG = 1 right before GPC and page 5 rises](2026-11-19-j81-ios-pregpc-miscacg-result.md); the Linux observer control read 0 in A/B/C
([paired run](2026-11-19-j81-observer-paired-result.md)). Martin approved one isolated Linux write test.

Change versus the observer campaign (diff: `2026-11-19-j81-linux-miscacg-write-campaign.diff`): after snapshot B (cycle and bridge plan done, GPC not yet requested)
a new step runs `pmgr-miscacg-set` (source `boot/pmgr-miscacg-set.c`, freestanding static aarch64, built with Homebrew LLVM 14 clang+lld):
- maps /dev/mem at 0x20e032000, reads the word, announces it, waits for `WRITE\n` from the harness;
- writes `1` only if the word reads exactly 0 (iPadOS' enableACG(true) is old|1 at this address), then reads back; any other pre-value: no write, exit 3;
- nothing else is touched (no GPU/GPC/bridge access, one store instruction).
Then snapshot B2 must show MiscACG = 1 and every other word equal to B, otherwise the campaign stops BEFORE the GPC batch. The paired GPC/page-5 batch and snapshot C follow unchanged.
Everything stays under the same boot-id checks. One shot per boot; no retry on the same boot.
Offline tests: `boot/test_j81_observer_miscacg_write_flow.py` (success, refused writer, post-write mismatch stopping before GPC).

Reading the result: page 5 rises with MiscACG = 1 -> the retained MiscACG bit is sufficient in this recipe (candidate fix). Page 5 stays 0 -> MiscACG = 1 alone is not
sufficient on Linux (iPadOS startup has other differences, e.g. the page-1/page-4 words 0x40480348/0x48480348 noted earlier).
