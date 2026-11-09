# J81 same-boot GFX perf-state comparison

Date: 2026-11-09. One guarded J81 Linux hardware session. The iPad was
reachable after the test; no RGX, GPC, bridge, or MCC register was accessed.

## Result

In one boot the first snapshot read PMGR GFX `0x20e020320 = 0x00000300`.
The previously tested one-shot consumer requested power-on (`rc=0`). The
second snapshot read `0x000003ff` (target and actual 15). Boot ID matched
across the sequence; afterward the consumer reported runtime status `active`
and usage 1, and the iPad answered another shell request.

All 34 perf-page words matched between snapshots: control
`0x20e01c200 = 0x80000000`, `0x20e01c300 = 0x40000001`, and both words of
all 16 table entries. States 1–8 had `+4` values `0x70, 0x70, 0x70, 0x80,
0x70, 0x70, 0x70, 0x80`; states 0 and 9–15 had `+4 = 0`. The main words
match the [earlier capture](2026-11-08-j81-gfx-perf-state-live-read.md).
This closes the prior *cross-boot* gap for those sampled words: their
before/after values match in this boot. It does not rule out a transient
change between snapshots, identify a selected performance state or clock,
or establish why the first GPU identity read stalled.

## Procedure and evidence limits

The payload `gcroot-gpu-pmgr-once-payload` passed its `SHA256SUMS` check.
Read-only preflight reported the expected kernel notes hash, the required
GFX no-poweroff DT guard, no existing module or consumer, and `/dev/mem`.
[`boot/gpu_pmgr_perf_pair.py`](../boot/gpu_pmgr_perf_pair.py) verifies the
staged hashes and boot ID, captures the first snapshot, requires PMGR
`0x300`, runs the existing host-acknowledged power wrapper, then captures
the second snapshot and requires `0x3ff`. Any failed stage stops the run.
The pair intentionally performs two snapshots in this boot, unlike the
single-snapshot tool's default one-per-boot guidance. Both snapshots use the
previously run archived executable, whose labels and hash match the saved
artifact; there is no reproducible build transcript tying that executable to
its adjacent source. Each snapshot has a host-side timeout, not a target-side
watchdog; a blocked MMIO transaction may require DFU recovery.

Raw logs are private in `artifacts/live/private/gpu-pair-20261109-a/`:

- `before.log`: SHA-256 `5163c24eac77909fe36ed29184c6c420d478b10320743fc85501e0fc052a4ee8`
- `power.log`: SHA-256 `5d95ebd9f6e8ee52b7d3e89960314f83c77bdeb29254ac0833cbe9a21c2b9c8f`
- `after.log`: SHA-256 `67788401e63691cf466d4ee8d2c6f7692a495bb263516fed4c5a1b2a4d483c90`

The raw files are not publicly available, so external readers cannot verify
the values from this note alone. Host-only checks cover expected values,
missing/duplicate labels, failed power, and boot changes; the actual device
run is separate evidence.
