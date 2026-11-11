# J81 selector-10 bridge readback

On 2026-11-11 a fresh cycle-payload Linux RAM boot
`288eb570-d96a-48cf-8ae0-321e9fba511c` passed the existing campaign
preflight, PMGR cycle, 66 bridge-store checkpoints, and GPC state-1 setup.
The [readback candidate](2026-11-11-j81-bridge-readback-candidate.md) then
ran once under the progress-gated watchdog:

```text
PMGR 0x20e020320:    0x000003ff
GPC state:           0x00000001
GPC control:         0x40000000
selector 10 +0x18:   0x80010004
stage=finished rc=0
stage=watchdog-disarmed
```

The newly sampled address was `0x201f80018`. It read back the value
`0x80010004` written for selector 10 in this boot's table sequence. The
host acknowledged each read; the watchdog disarmed and the iPad answered
ping afterward. This provides one additional readback, but not iPadOS
readback, semantics for the high bits, retention of the other 64 table
entries, or evidence that the GPU core is accessible. Selector 9's
corresponding value was read on an earlier test4 boot, not this boot.

The target read completed once; that does not prove it is harmless in other
states or that another bridge address is safe. The test did not read the
GPU core or write new bridge values beyond the existing setup sequence.
Raw logs remain private in `artifacts/live/gpu/bridge10-20261111-01/`.

The test source is `boot/gpu-bridge10-postgpc.c`, host capture is
`boot/gpu_bridge10_postgpc_capture.py`, and the build is flake output
`gpu-bridge10-postgpc-static`. Host tests exercise one-shot and read-only
mapping guards, acknowledgments, result parsing and out-of-order rejection.
