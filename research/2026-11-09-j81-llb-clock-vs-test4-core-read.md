# J81 LLB clock setup versus test4's stalled RGX read

Date: 2026-11-09. Offline comparison of the local 12B410 LLB analysis,
Linux test4 artifacts, and the expanded perf capture. No device access.

## One concrete boot-stage difference

LLB's normal startup path reaches the setup routine at `0x180012c64`;
following the GFX perf-table writes, that routine polls PMGR `0x20e005000`
bit 25, clears bit 0 at `0x20e005004`, sets bit 24 at `0x20e005008`, and
sets bit 31 in `0x20e01c200`. The instruction-level observations and
reachability are recorded in
[`2026-11-08-j81-llb-pmgr-write-scan.md`](2026-11-08-j81-llb-pmgr-write-scan.md).

Linux test4 explicitly cycles GFX power, replays selector tables 9 and 10,
initializes GPC, then attempts RGX identity at `0x201000020`. Its helper
source (`boot/gpu-core-revision-once.c`) reads PMGR power, GPC state and
control before that attempt; it contains no operation on `0x20e005000`,
`0x20e005004` or `0x20e005008`. The test4 capture confirms PMGR state
`0x3ff`, GPC state `1` and control `0x40000000`, then stalls at the identity
read (see [`2026-11-07-j81-core-revision-after-clock-test4.md`](2026-11-07-j81-core-revision-after-clock-test4.md)).
Therefore the tested sequence did not explicitly replay LLB's three
`0x20e005xxx` operations. Because test4 used the documented DFU → PongoOS →
m1n1 → Linux route, LLB is not part of that recorded handoff
([handoff boundary](2026-11-08-j81-llb-linux-perf-state-boundary.md)).

This is a source-backed difference in setup history, not evidence that the
three writes are required for RGX access: the private LLB analysis does not
name the block as GFX/PLL, and the test4 log contains no readback of those
addresses. Do not infer that test4's bootloader state lacked the configuration;
there is no pre-test4 snapshot. The 2026-11-09 expanded perf capture reads
the GFX table/control and power-state word, but not `0x20e005xxx`, so it does
not close this gap.

## Boundary

The follow-up perf capture's provenance transcript records hashes for its
raw log, archived probe source, and binary; matching output labels make the
log consistent with those artifacts, but no build transcript proves the
source-to-binary link. The log also lacks an explicit device or boot
identifier. It is evidence for the reported PMGR values, not for the
PLL-related setup state or the cause of the stalled access (see
[`expanded capture audit`](2026-11-09-j81-expanded-perf-capture-audit.md)).
No new register access or replay is proposed: the available evidence does
not make writing these PMGR addresses safe or establish that they are an
RGX prerequisite.
