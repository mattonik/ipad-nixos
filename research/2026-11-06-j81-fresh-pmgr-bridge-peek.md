# J81 fresh PMGR and bridge readback

After a fresh DFU/PongoOS/Linux handoff, the reviewed PMGR transition and
read-only bridge peek were run once each.

PMGR capture:

```
pre-read  0x00000300 (target=0, actual=0)
power     rc=0
```

Watchdog-supervised readback:

```
PMGR      0x000003ff (target=15, actual=15, auto=0, reset=0)
GPC       0x00000000
bridge    0x201f00018 -> 0x00000004
watchdog  disarmed normally
```

Private capture hashes:

* `2026-11-06-pmgr-power-test-12.log`: `46d0c1fe8e652bd43433a48b0bbe391e471199a815f7aa278674704fd858d485`
* `2026-11-06-gpu-bridge-peek-02.log`: `e97a805b3f1b07f720cf5acfa7b6985f24c65d6e365d6afd85cb9acdac864dd4`

The bridge readback is stable at `0x4` across fresh boots. No bridge write,
GPU-ID read, firmware, GPC initialization, or rendering was attempted.
