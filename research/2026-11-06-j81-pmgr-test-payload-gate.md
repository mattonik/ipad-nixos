# J81 PMGR test-payload gate

The failed insertion was not a bad module build for the intended test image.
It was attempted against `result-hoolock-control`, whose kernel does not carry
the experimental J81 PMGR test node/export (`j81_gpu_pmgr_failstop_v1`). A
module rebuilt against that control kernel therefore cannot provide the
one-shot test consumer; the control DT also lacks the guarded test node.

The repository already contains the matching pair from the dedicated test
derivation:

```
artifacts/live/gcroot-gpu-pmgr-once-payload/m1n1-linux.bin
artifacts/live/private/gpu-test-staging/gpu-pmgr-once.ko
```

The staged module was built against the test kernel's patched PMGR provider,
not the ordinary control payload. The correct sequence is therefore:

1. enter DFU and boot the pinned diagnostic PongoOS;
2. load `gcroot-gpu-pmgr-once-payload/m1n1-linux.bin`;
3. verify the module hash and live kernel-notes hash;
4. run the existing fail-stop capture, which acknowledges the `0x300` PMGR
   baseline before issuing its single `POWER` request.

No Linux-side reboot was issued. The iPad remains on the known-good control
image; no additional hardware state change occurred after the rejected module
insert.

