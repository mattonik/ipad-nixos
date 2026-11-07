# J81 core revision read after full clock sequence

On fresh cycle-payload RAM boot `4e5be4df-c215-40ee-b6db-21b2bc8fd932`, the PMGR cycle succeeded, all 66 selector 9/10 writes reached their after-write checkpoints, and GPC initialization returned state 1. Post-GPC bridge readback was `0x80010004` at `0x201f00018` and `0x00010001` at `0x201f0001c`, matching test3.

The supervised single-read probe armed the 20-second watchdog, passed both PMGR checks (`0x3ff`), read GPC state `1` and control `0x40000000`, and emitted `stage=before-gpu-revision address=0x201000020 width=32`. The host sent `READ`. No after-read or watchdog-disarm checkpoint arrived; the capture ended incomplete and USB-network ping failed afterward.

This reproduces the earlier revision-read stall after the full clock tables. It shows that these table writes plus the tested GPC initialization are not sufficient for a completed read under this sequence. It does not prove why the read failed or whether the watchdog reset the device. Do not retry in this boot.

Captures: `artifacts/live/gpu/clock-cycle-20261107-test4.log`, `clock-table-20261107-test4.log`, `gpc-init-20261107-test4.log`, `postgpc-bridge-20261107-test4.log`, and `core-revision-20261107-test4.log`.
