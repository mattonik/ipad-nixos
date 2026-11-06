# J81 bridge readback result

The first operator-present bridge readback completed after a fresh PongoOS/Linux handoff.

- PMGR power transition: `rc=0`; guarded PMGR read `0x000003ff` (`target=15`, `actual=15`).
- GPC pre-state: `0x00000000`.
- Read-only bridge register `0x201f00018`: `0x00000004`.
- Watchdog: armed for 20 seconds and disarmed normally.
- Capture SHA-256: `e97a805b3f1b07f720cf5acfa7b6985f24c65d6e365d6afd85cb9acdac864dd4`.

This is a useful readback baseline for the earlier five-write segment. It does not identify the GPU or establish firmware execution; no firmware, META, GPC initialization, or rendering was attempted.
