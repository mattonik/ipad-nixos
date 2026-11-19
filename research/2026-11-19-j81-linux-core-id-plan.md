# J81 Linux gated core-ID read after the MiscACG write: plan (2026-11-19)

Basis: with MiscACG = 1 stored before GPC, page-5 bit 30 rises on Linux in two of two boots ([result](2026-11-19-j81-linux-miscacg-write-result.md)). The campaign never read the RGX core ID.
On iPadOS the same conditions give core ID 0x00070500 at 0x201000020. On Linux that read always hung while page 5 was clear.

What is added (diff: `2026-11-19-j81-linux-core-id-campaign.diff`, on top of the MiscACG-write campaign): after snapshot C and after summary.txt is already on disk,
the pinned `gpu-watchdog-supervisor --core-revision-cycle` runs the new reader `boot/gpu-core-id-gated.c` (freestanding static aarch64, built with Homebrew LLVM 14 clang+lld) through the wrapper `boot/gpu-core-id-gated-run.sh`.
- Only 32-bit /dev/mem READS through PROT_READ mappings, each announced and acknowledged by the host (READ), each result fed to the watchdog (FEED n). No store can reach hardware.
- Order and gates: GFX PS 0x20e020320 == 0x3ff, MiscACG 0x20e032000 == 1, page 5 0x20e005004 bit 30 set, GPC state 0x201e01000 == 1; GPC control 0x201e00000 logged only; then the core ID 0x201000020.
  Any failed gate prints `stage=skipped reason=...` and finishes cleanly without touching the core window (no watchdog reset).
- If the core read hangs the bus, the supervisor's 20 s hardware watchdog resets the iPad; the earlier results are already on disk and the capture log is fsynced. One shot per boot (mkdir marker).
- The harness feeds the watchdog only for expected checkpoints in the expected order; anything else stops feeding.
Offline tests: `boot/test_j81_observer_core_id_flow.py` (full read -> 0x00070500, gated skip with no core access, reordered checkpoint -> no feed), updated `test_j81_observer_miscacg_write_flow.py`.
Untested on the device: the reader binary itself (no aarch64 emulator here); its first real run is the experiment.
Reading the result: a plausible core ID (iPadOS: 0x00070500) means the MiscACG-then-GPC recipe makes the core window respond on Linux. A hang/reset, 0 or 0xffffffff would show the core window still needs another step.
