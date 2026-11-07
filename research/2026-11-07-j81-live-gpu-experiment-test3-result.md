# J81 clock-table and post-GPC observation

On a fresh cycle-capable RAM boot (`a535c83a-ff8d-4657-a124-9973918f1505`), the guarded PMGR cycle completed, all 66 selector 9/10 writes reached their after-write checkpoints, and GPC initialization returned state `0x00000001`.

The supervised post-GPC read completed and disarmed the watchdog:

| Register | After tables and GPC init | Prior post-GPC baseline without full tables |
| --- | --- | --- |
| `0x201f00018` | `0x80010004` | `0x00000004` |
| `0x201f0001c` | `0x00010001` | `0x00010001` |

This demonstrates that the first table value remained readable after GPC init. The second observed register matched the earlier baseline. The runs are separate boots; this does not establish the meaning of the changed bits or whether GPU-core access is safe. No RGX ID read or firmware execution was attempted.

Captures: `artifacts/live/gpu/clock-cycle-20261107-test3.log`, `clock-table-20261107-test3.log`, `gpc-init-20261107-test3.log`, and `postgpc-bridge-20261107-test3.log`.
