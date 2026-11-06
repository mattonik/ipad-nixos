# J81 Fender wake candidate

The next hardware candidate is now packaged as `gpu-fender-wake`. It is a
one-shot, post-PMGR-cycle experiment that maps only the Fender/GPC window at
`0x201e00000..0x201e20fff`; it never reads or writes the RGX identity address.

The sequence is fail-closed and host-acknowledged: initial state zero, reset
(`+0x20000=0`), bounded bit-4-clear poll, request state `0x10`, bounded
zero-state poll, hold (`+0x20000=0x20`) with readback, then the known wake
writes (`+0x10000=0xffff0000`, `+0=0x40000000`, `+0x1000=0x11`) and a bounded
final poll. A one-shot guard consumes the boot on any attempt.

Offline validation:

```text
python3 boot/test_gpu_fender_wake.py
python3 tools/check_offline.py   # 82 passed, 0 failed, 7 skipped
```

Build when the shared builder has at least 15 GB free on the Mac:

```text
./tools/builder.sh build --wait --who j81-fender-wake \
  nix build .#packages.x86_64-linux.gpu-fender-wake-static \
  -o artifacts/live/gpu-fender-wake
```

After the existing PMGR cycle capture succeeds in the same boot, the host
collector is `boot/gpu_fender_wake_capture.py`; its log is append-only and
must be retained under `artifacts/live/gpu/`. Do not run this unattended: it
contains MMIO writes and is the first reset/hold experiment after the known
safe GPC bridge boundary. A separate RGX read remains explicitly excluded.
