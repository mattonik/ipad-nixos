# J81 PMGR reset-generation test ready

The next hardware artifact is now built and host-validated. It uses the exact
diagnostic kernel ABI already used by the successful PMGR/GPC tests.

Artifacts:

```
artifacts/live/gpu-pmgr-cycle/gpu-pmgr-cycle.ko
  sha256 c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23
artifacts/live/gpu-pmgr-cycle/payload/m1n1-linux.bin
  sha256 3dd234b5f20c85b71873a148463e5d6a682c232c1bdef9f5b5f3ea2d8ed96835
boot/gpu-pmgr-cycle-run.sh
  sha256 e21f678dd41064d865b9946a0a6c9002166ea573ed48500e9748fe0e0e848d62
```

The derived DTB is identical to the PMGR test payload except that it removes
`experimental,j81-gpu-test-no-poweroff`; the provider's fail-stop/error patch
and kernel notes remain the same. The module is one-shot: it requires PMGR
baseline `0x00000300`, takes one runtime-PM reference, performs one
`pm_runtime_put_sync()` off transition, reacquires the reference, and leaves
the final lease held. No GPU MMIO is present in the module.

Host checks passed:

```
python3 boot/test_gpu_pmgr_cycle.py
python3 boot/test_gpu_pmgr_cycle_capture.py
```

Hardware command after booting the cycle payload and staging the module,
wrapper, and existing read-only `gpu-pmgr-peek` helper:

```
python3 boot/gpu_pmgr_cycle_capture.py \
  artifacts/live/gpu/pmgr-cycle-$(date +%Y%m%d-%H%M%S).log \
  c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23 \
  82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 \
  --timeout 40
```

This test is operator-present only. A failed or incomplete capture consumes
the boot; do not retry it. The GPC wake writes and all RGX reads remain a
separate later step.
