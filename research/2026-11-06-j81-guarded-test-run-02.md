# J81 guarded bridge test run 02

Fresh Linux session reached over the existing USB network (the PongoOS USB control interface was not needed once `172.16.42.1` answered). The hash-checked PMGR module and diagnostic bundle were staged over SSH.

- PMGR pre-transition read: `0x00000300` (`target=0`, `actual=0`, `auto=0`, `reset=0`)
- PMGR power transition: `rc=0`
- Guarded bridge PMGR read: `0x000003ff` (`target=15`, `actual=15`, `auto=0`, `reset=0`)
- GPC pre-state: `0x00000000`
- Five bridge writes completed with the expected values; child returned `rc=0`.
- Watchdog armed for 20 seconds and disarmed normally.
- Capture: `artifacts/live/private/gpu-observations/2026-11-06-gpu-bridge-segment-07.log`
- Capture SHA-256: `1e53a2f807c186e6d67c78da17768197d25c9f99e4b5d17be4cba5c4cb7b71cb`

This confirms the guarded PMGR/bridge test is repeatable from a fresh Linux session. No firmware, META, GPU-ID, GPC initialization, or rendering was attempted.
