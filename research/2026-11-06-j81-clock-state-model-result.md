# J81 Apple GFX clock-state model result

The execution-disabled model now validates the recovered Apple 8.1 GFX
clock record and bridge tables from
`artifacts/live/private/gpu-offline/gfx-bridge-static-plan.json`.

Validated metadata:

```
device id             0x7c
power-state index     100
special flags         0x06
bridge selectors      9, 10
selector 9 base       0x201f00000 (33 pairs)
selector 10 base      0x201f80000 (33 pairs)
total pairs           66
table digest           b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4
```

The modeled enable trace is:

```
PMGR target 15
flush power-state index 100
apply selector 9 (abstract only)
apply selector 10 (abstract only)
provider busy transition
GPC setup and bounded poll; require state 1
```

The clock special-action helper applies the selector tables only on enable;
disable performs the provider busy transition without replaying the tables,
then flushes the power-state index and returns PMGR to state 0. The model rejects a zero clock reference and emits no MMIO
operations. The table validator checks word alignment, each bridge window's
`0x81000` extent, exact base-plus-offset mapping, and global non-overlap.

The busy transition adjusts a reference count; its display idle-control call
is conditional on runtime framebuffer-cache state and a 0-to-1 or 1-to-0
edge. It must not be assumed to run on every GPU clock transition. See the
framebuffer-cache trace in `2026-11-04-j81-gpu-offline-trace.md`.

The live result (`PMGR actual=15`, `GPC state=0`) means the first four
abstract prerequisites are not equivalent to a ready GPC on Linux; the final
GPC setup/poll remains unresolved. Therefore this model is a planning and
validation artifact, not authorization to replay the 66 writes.

