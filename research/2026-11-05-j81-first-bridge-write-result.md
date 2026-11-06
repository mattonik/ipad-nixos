# J81 first bridge write result

The first guarded write completed on a fresh RAM boot without a reset or lost
connection.

- PMGR read: `0x000003ff`, target/actual 15
- GPC state before write: `0x00000000`
- Single write: `0x80010004` to `0x201f00018`
- Watchdog: armed for the transaction, then disarmed normally
- Post-write state: iPad responsive; GFX runtime `active`, usage `1`

This is only a software completion marker. No readback was attempted, so it
does not prove the write took effect or that the bridge is safe to continue.
No second write, GPC initialization, GPU ID read, firmware, or rendering was
attempted in this boot.

Private capture: `artifacts/live/private/gpu-observations/2026-11-05-bridge-first.log`

Capture SHA-256:
`a35d9b254cdea4b316a28a9b2e9ab9436f0818f4ef3cab5fcabbe713a7681342`
