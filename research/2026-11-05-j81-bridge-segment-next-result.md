# J81 selector-9 next segment

On a fresh RAM boot, the next guarded segment completed cleanly:

| address | value |
|---|---:|
| `0x201f00018` | `0x80010004` |
| `0x201f40010` | `0x007c7901` |
| `0x201f40014` | `0x007c7c01` |
| `0x201f40018` | `0x007c7c01` |
| `0x201f4001c` | `0x007c7c01` |

PMGR remained `0x000003ff`, GPC state was `0`, the watchdog disarmed, and the
iPad remained responsive with GFX runtime usage `1`.

These are CPU-side completion markers only; no readback, GPC initialization,
GPU ID read, firmware, or rendering was attempted.

Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-bridge-segment-9-next4.log`

Capture SHA-256:
`258ffb19e07a69a334fde00690cf0c2ab8440df027ccc34f567747ac3393f3f6`
