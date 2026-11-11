# J81 DWI-first GPC and PMU comparison result

On 2026-11-11 fresh cycle-payload Linux RAM boot
`27a29549-0cd1-4057-a7bc-4599d87ebf3c`, the
[prepared comparison](2026-11-11-j81-dwi-gpu-comparison-test.md) completed.
Preflight and pinned hashes passed. The tool switched DWI from `0x200` to
`0xff`; a further sample after the PMGR cycle and bridge writes, immediately
before the supervised GPC stage, was `0xff`.

| Observation | Before GPC | After GPC | About 10 s later |
| --- | --- | --- | --- |
| DWI PS `0x20e020120` | `0x000000ff` | `0x000000ff` | `0x000000ff` |
| PMGR `0x20e02300c` | `0x00000000` | `0x00000164` | `0x00000164` |
| PMU row `0x0128`, bytes 0 and 2 | `0x00`, `0x40` | `0x64`, `0x64` | `0x64`, `0x64` |
| PMGR `0x20e005004` | `0x00000000` | `0x00000000` | `0x00000000` |
| PMGR `0x20e01c200` | `0x80000000` | `0x80110100` | `0x80110100` |

The post-GPC row reads were separate I2C transactions, not simultaneous
samples with the PMGR words. Before DWI activation, the PMU `0x0128` bytes
were also `0x00`, `0x40`, and PMGR `0x2300c` was zero. The CPU-associated
PMU row `0x0100` changed from `0x9c`/`0x9c` before DWI activation to
`0x6d`/`0x6d` after; this is consistent with the previously observed DWI
correlation, not a direct voltage measurement.

The watchdog-supervised GPC batch reported state `1` on poll 11. The
request-to-success sample was bracketed at approximately 294.3–295.1 µs.
Page-5 `+4` returned zero at the first sample, less than 709 ns after the
poll load, and again at the later sample, less than 101,834 ns after the
poll load. The watchdog disarmed, the remaining snapshots completed, and the
iPad answered ping. No GPU-core read or page-5 write was made.

This is the first captured J81 boot in which the candidate PMU row changed
to `0x64` after a GPC request with DWI on. Together with the matching PMGR
word transition, it supports a relationship between this state request and
the candidate PMU row. It does not independently establish the physical rail,
actual voltage, byte semantics or exactly when either changed; other work
between the snapshots could contribute. Page-5 bit 30 stayed clear at both
captured GPC boundaries and later samples despite the PMU row's change. Thus
a missing update to these particular PMU bytes is not sufficient to explain
that observed page-5 difference on this boot. It does not prove the rail or
all other power prerequisites are correct, or identify why GPU core access
stalls. Linux DWI was manually enabled and its state was sampled rather than
monitored continuously.

Raw logs, including the PMU reads, are private at
`artifacts/live/gpu/dwi-gpu-compare-20261111-01/`. The test used `i2ctransfer
-f` with a register-address selection followed by eight-byte reads. No full
PMU dump or PMU value-write command was performed; reads can still have
side effects.
