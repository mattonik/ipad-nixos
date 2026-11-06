# J81 selector-9 five-pair repeat

On a fresh RAM boot, the guarded selector-9 segment completed again without a
reset or lost connection. The PMGR word was `0x000003ff` (target/actual 15),
and the pre-write GPC state was `0`.

| address | value |
|---|---:|
| `0x201f00018` | `0x80010004` |
| `0x201f40000` | `0x007c7c01` |
| `0x201f40004` | `0x007c7c01` |
| `0x201f40008` | `0x007c7c01` |
| `0x201f4000c` | `0x007c7901` |

The watchdog disarmed normally and Linux stayed responsive. This is a repeat
of the previously recorded first selector-9 segment, strengthening that these
CPU-side writes are stable under the guarded test path. No GPC post-read,
selector 10, firmware, GPU ID read, or rendering was attempted.

Private capture:
`artifacts/live/private/gpu-observations/2026-11-06-gpu-bridge-segment-01.log`

Capture SHA-256:
`8005fd10145faebb455741bad6dffc8cae90a11f0476ff41f41c378ba0715450`
