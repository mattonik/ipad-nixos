# J81 post-GPC bridge read test ready

Because the RGX revision read still hangs after the PMGR cycle and GPC wake,
the next hardware test stays entirely in the known-good Fender/bridge windows.
The new static probe reads, in order:

```
GPC +0x1000  (must be 0x00000001)
GPC +0x0000  (must have bit 29 clear)
bridge +0x18
bridge +0x1c
```

It never maps or accesses `0x201000000`, performs no writes, and is one-shot.
The ARM64 static binary is ready:

```
artifacts/live/gpu-bridge-postgpc/gpu-bridge-postgpc
sha256 b43aa32902eea641350715f5ad9dd6f3275a711877460135825c3409dcab2876
wrapper boot/gpu-bridge-postgpc-cycle-run.sh
```

After a fresh cycle-payload boot, stage the binary as `/tmp/gpu-bridge-postgpc`,
stage the wrapper as `/tmp/gpu-bridge-postgpc-cycle-run`, and run:

```
python3 boot/gpu_bridge_postgpc_capture.py \
  artifacts/live/gpu/postgpc-bridge-$(date +%Y%m%d-%H%M%S).log \
  b43aa32902eea641350715f5ad9dd6f3275a711877460135825c3409dcab2876 \
  --timeout 30
```

Host validation passed and the complete offline suite remains 82 passed, 7
input-dependent skips. A failed or incomplete capture consumes the boot; do
not retry it.
