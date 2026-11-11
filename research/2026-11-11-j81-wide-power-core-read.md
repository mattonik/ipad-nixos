# J81 core-ID read after 20-domain restore

On 2026-11-11 the user authorized a further hardware attempt on the existing
wide-power RAM boot `00ef6863-e756-417e-a9b9-f27705b35d6b`. After the
[20-domain comparison](2026-11-11-j81-wide-power-result.md), a fresh
host-checked snapshot found all 20 target/actual nibbles active and the three
checked external parents active. The boot ID still matched. The single-core
revision probe and cycle wrapper were staged from the pinned bundle, and
its host capture and watchdog supervisor tests passed before use.

The watchdog-supervised read emitted, in order:

```text
stage=watchdog-armed timeout=20
stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0
stage=after-pmgr-read raw=0x000003ff
stage=after-gpc-state raw=0x00000001
stage=after-gpc-control raw=0x40000000
stage=before-gpu-revision address=0x201000020 width=32
READ
```

No `after-gpu-revision`, success, or watchdog-disarm marker arrived. The host
capture timed out, and USB networking subsequently did not respond. The
record establishes that the host acknowledged the read checkpoint, not that
the CPU successfully issued the MMIO transaction or that a specific fault
occurred. The device's exact reset/recovery behavior and the domains' state at
the transaction are not established. No value may be inferred from the
missing response.

This is the first direct core-read attempt after the full 20-domain restore.
It reproduces the earlier non-completion despite the prior checkpoints, so
restoring these domains in this boot did not produce a captured working ID.
It does not prove the power domains stayed active continuously, that the GPU
was otherwise fully initialized, that page-5 bit 30 is causal, or that no
other clock/reset/firmware state matters. Do not repeat on this boot. Raw
capture and pre-read domain snapshots remain private under
`artifacts/live/gpu/wide-power-core-read-20261111-01/`.

After the capture timed out, the user reported that the iPad had rebooted
into iPadOS. This confirms recovery to iPadOS by user observation, but the
capture does not identify whether the watchdog or another reset mechanism
caused the reboot. The Mac did not enumerate the device when checked afterward;
no additional device access or GPU test was performed.
