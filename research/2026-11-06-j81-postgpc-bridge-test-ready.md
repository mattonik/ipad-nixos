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

## 2026-11-06 hardware result

The test completed after the verified PMGR off/on cycle and GPC init:

```
PMGR after cycle: raw=0x000003ff (target=15, actual=15)
GPC state:        0x00000001
GPC control:      0x40000000 (bit 29 clear)
bridge +0x18:     0x00000004
bridge +0x1c:     0x00010001
finished rc=0
```

Capture: `artifacts/live/gpu/postgpc-bridge-20261106-164615.log`
SHA-256: `aa4019e566a73f5eb95f5081866d1c03c911849f6bd8469770e4aa8568c563c1`

This confirms that the post-GPC bridge window remains readable and stable on
the iPad. It does not establish that the RGX core is powered or firmware-ready;
the first read at `0x201000020` remains intentionally out of scope.
