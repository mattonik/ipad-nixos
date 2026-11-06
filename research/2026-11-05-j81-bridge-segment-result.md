# J81 selector-9 first segment

On a fresh RAM boot, the watchdog-supervised five-entry segment completed
without a reset or lost connection:

| address | value |
|---|---:|
| `0x201f00018` | `0x80010004` |
| `0x201f40000` | `0x007c7c01` |
| `0x201f40004` | `0x007c7c01` |
| `0x201f40008` | `0x007c7c01` |
| `0x201f4000c` | `0x007c7901` |

The PMGR word was `0x000003ff`, GPC state was `0`, and the watchdog disarmed
normally. The iPad remained responsive with GFX runtime state `active` and
usage `1` afterward.

This confirms only that these writes completed from the CPU side. No readback,
second segment, GPC initialization, GPU ID read, firmware, or rendering was
attempted in this boot.

Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-bridge-segment-9-first5-success.log`

Capture SHA-256:
`8005fd10145faebb455741bad6dffc8cae90a11f0476ff41f41c378ba0715450`
