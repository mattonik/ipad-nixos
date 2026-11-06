# J81 fresh bridge peek result

After a fresh DFU/PongoOS/Linux handoff, the guarded read-only bridge probe
completed under the watchdog:

```
PMGR:        0x000003ff (target=15 actual=15 auto=0 reset=0)
GPC state:   0x00000000
bridge +18:  0x00000004
finished rc=0
watchdog-disarmed
```

The host capture is `artifacts/live/gpu/bridge-peek-20261106-152848.log` with
SHA-256 `9e45e28c1e9fb3d7c6fb012df770e282260815f0ebe315f6e7b36e4092f480a5`.
This confirms the bridge window remains readable on a fresh boot without
repeating the unsafe GPU-core revision read at `0x201000020`.
