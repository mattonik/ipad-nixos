# J81 supervised bridge peek

Date: 2026-11-05

The first supervised, read-only hardware observation completed without a
reset or lost connection. The host collector persisted every checkpoint and
the watchdog disarmed after normal completion.

## Observation

| checkpoint | result |
|---|---|
| PMGR word `0x20e020320` | `0x000003ff`, target 15, actual 15, auto 0, reset 0 |
| GPC state `0x201e01000` | `0x00000000` |
| bridge read `0x201f00018` | `0x00000004` |
| watchdog | armed for the transaction, then disarmed normally |
| GFX runtime state | `active`, usage `1` after the test |

The read was performed through the verified RAM-root wrapper and its one-shot
guard. No bridge writes, GPC initialization writes, GPU revision read, or
firmware execution occurred. The result is a register observation only; it
does not establish that replaying the Apple bridge tables is safe.

## Reproducibility

- probe SHA-256: `52cd0d9d7e79a52f57d1b65137533a4b95a8928f1c1beb3b9b2fafeec005e0de`
- supervisor SHA-256: `124c906fe3a3cefca2464532e10012751396fde7eb89fc30891e21eb84081219`
- wrapper SHA-256: `1e807ad156199dba1d7f739be8515e65bfa88b311efa0cb8afa7dbbad9023285`
- private capture: `artifacts/live/private/gpu-observations/2026-11-05-bridge-peek.log`
- capture SHA-256: `843a74576477af3d23c494fabdec2fc29443c3f972e28f4e382c9a4a67bbe8b9`

The private capture is intentionally ignored by Git. The next step is static
analysis of what `0x4` means in the two J81 Apple bridge tables and the A9
driver before considering any write experiment. Do not retry the read in this
boot or infer a successful GPU power-up from it.
