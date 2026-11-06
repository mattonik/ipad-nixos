# J81 GPU identity read boundary

The bounded, read-only identity probe was run after the successful GPC state-1
transition. It confirmed:

```
PMGR:      0x000003ff (target=15 actual=15 auto=0 reset=0)
GPC state: 0x00000001
GPC ctrl:  0x40000000
```

The first GPU-core read, revision at `0x201000020`, was acknowledged but never
returned. The USB/Linux link then disappeared. The host capture is
`artifacts/live/gpu/gpu-id-20261106-150528-final.log` with SHA-256
`e88d6d3e52410911dfb7a37daf1141d94055652e70c768ca2822265fa2919d97`.

No GPU identity value was obtained. Do not retry this boot; recover with a
normal hardware restart/DFU cycle. This establishes that the GPC state-1
initialization is repeatable, but the legacy GPU-core window is not yet safe to
read at `0x201000020`.
