# J81 expanded GFX perf-state capture audit

Date: 2026-11-09. Audit of the expanded read-only capture and the 2026-11-08
baseline. No device was accessed for this audit.

## Result

The expanded capture reports PMGR power-state word `0x20e020320 = 0x000003ff`
(target/actual state 15), versus `0x00000300` (target/actual state 0) in the
2026-11-08 baseline. The control word stayed `0x80000000`. All 16 table words
at `0x20e01c000 + n*0x10` match exactly across the two logs: states 0 and
9–15 are zero; states 1–8 are `6436d063, 7024b021, 7027d031, 7f313061,
6436d067, 7024b023, 7027d033, 7f313063`.

The baseline did not read each entry's `+4` word or `0x20e01c300`. The
expanded capture reports `+4` values `0,70,70,70,80,70,70,70,80,0,0,0,0,0,0,0`
(hex) and `0x20e01c300 = 0x40000001`; there is no pre-transition measurement
for those fields, so their stability cannot be compared. A separate
2026-11-09 after-power log independently repeats the matching power-state,
control, and table values.

This establishes the reported PMGR power-state word and table contents for
these reads. It does not identify a selected GPU performance state or its
clock rate.

## Capture and provenance limits

The expanded raw log contains a complete `READ` response, `stage=after-perf-read`,
`rc=0`, and a subsequent shell `alive` response. Its output labels match the
archived capture source `artifacts/live/gpu-pmgr-perf-v2/p.c` and the strings
in the archived aarch64 executable. SHA-256: source
`fa65361571e06b235da883385212d96b88a25b5d02ab597f217f4d7b49461de8`, binary
`d2ef11e1517d9cd70f8cdf174878604c7a10d9efb3116521b1cfbd132e187f84`, log
`306ae8f76a1ea75f0cf688e880efa87861a093e411d05dc09f0c11bc0a164d57`.
The source uses `/dev/mem` opened `O_RDONLY` and `mmap` with `PROT_READ`.

The archived source emits labels `w300` and `perfNN+4`; the current tracked
probe source emits `perf-tunable` and `perfNN-p4`. Thus the log is consistent
with the archived source/binary artifacts, but not label-for-label with the
current tracked source. No build transcript or reproducible build metadata
ties the archived executable cryptographically to that source. The raw
capture also lacks an explicit device identifier, boot identifier, kernel
identity, and wall-clock timestamp; local file modification time is not a
substitute for those facts. The 2026-11-08 baseline artifact is
`artifacts/live/gpu-pmgr-perf/20261108-perf-peek.log`; raw captures remain
private and are not included in this note.
