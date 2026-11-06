# J81 GPC state-1 initialization result

Date: 2026-11-06

After a fresh DFU/PongoOS/Linux boot, the verified PMGR consumer was loaded and
the single guarded GFX power request completed with `rc=0`. The bounded GPC
candidate then passed every checkpoint:

```
PMGR before: 0x00000300
PMGR after:  0x000003ff (target=15 actual=15 auto=0 reset=0)
GPC +0x1000 initial: 0x00000000
GPC +0x10000 write/readback: 0xffff0000
GPC +0x0000 write/readback: 0x40000000
GPC +0x1000 request/readback: 0x00000011
GPC +0x1000 poll-00: 0x00000001
finished rc=0
```

The raw host capture is `artifacts/live/gpu/gpc-init-20261106-150345-final.log`
with SHA-256
`eaa64207bdab0a8aa138d2f26193fb239983dd06c73601911944476d93090dbf`.
The PMGR capture is `artifacts/live/gpu/pmgr-power-20261106-150339.log` with
SHA-256 `46d0c1fe8e652bd43433a48b0bbe391e471199a815f7aa278674704fd858d485`.

The final live state was `runtime_status=active`, `runtime_usage=1`, with the
one-shot guard present. This is the first confirmed J81 GPC state transition;
GPU identity, firmware/META startup, bridge replay, and rendering remain
untested.
