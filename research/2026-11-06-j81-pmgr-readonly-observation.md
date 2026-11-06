# J81 PMGR read-only observation

Date: 2026-11-06

After loading the existing `result-hoolock-control` m1n1/Linux payload, the
USB shell came up on `172.16.42.1`. I uploaded only the static
`gpu-pmgr-peek` helper to `/tmp` and performed its single guarded read of
`0x20e020320`. The helper is read-only: it opens `/dev/mem` with `O_RDONLY`,
maps the PMGR page read-only, and waits for an explicit host acknowledgement
before the read.

Observed output:

```
stage=before-pmgr-read address=0x20e020320 width=32
stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0
```

The helper SHA-256 on the iPad matched the staged artifact:

```
78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd
```

No PMGR consumer module was inserted, no runtime-PM request was made, and no
GPU/GPC address was accessed. The `0x300` value is a useful baseline for the
fresh Linux payload, but is not by itself evidence that a power transition is
safe or that the GPU is initialized.

## Result

- Linux USB transport: **pass**.
- Guarded PMGR read: **pass**, value `0x00000300`.
- GPU/GPC MMIO, PMGR writes, firmware, and rendering: **not attempted**.

