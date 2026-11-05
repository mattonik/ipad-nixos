# J81 GPU overnight work: 2026-11-05

The overnight work left the iPad running the dedicated test kernel with the
GPU power diagnostic attached but suspended. At the final 07:28 Bratislava
check, Linux reported the GFX domain `off-0`; the running kernel notes and
loaded module build-ID note matched the test artifacts. The previous
acknowledged PMGR read on this boot returned `0x00000300`. The module's
one-shot power attribute has not received a valid power request.

The test kernel, matching AArch64 module and RAM-boot payload were built and
verified against the known-good control. Inert attachment was tested on the
iPad, invalid requests were rejected, and the existing-module path completed a
live dry run through the persisted pre-power checkpoint with `NO` in place of
`POWER`. As long as this same boot remains running, the guarded path can use
the loaded module without another DFU. The loaded build-ID note is an identity
check, not proof against malicious changes to module code. Full artifact
hashes, checks and private capture locations are in
[the GPU test batch](2026-11-04-j81-gpu-test-batch.md).

The firmware research identified additional differences between the 8.1 and
15.8.8 Apple loaders and the pinned Linux PowerVR loader:

- Both Apple releases skip certain core-memory zero records that Linux treats
  differently. Each firmware has a record crossing the Apple guard boundary.
- The thread-record words that look like possible stack addresses lie inside
  zero records that Apple's loaders skip; those records do not establish that
  the contents were initialized.
- Apple carries the secondary-thread record into a second structure. The two
  releases retain the same local word order and a common bootloader-address
  constant, while the observed field offsets differ by `0xf0`.
- The 8.1 initializer builds two views from an allocation at a common offset;
  their exact types, address domains and final firmware consumer remain open.

The evidence and limitations are in
[the offline trace](2026-11-04-j81-gpu-offline-trace.md). The LDR inspector
now checks these structural facts without exporting the proprietary images.
The final offline suite passed 56 checks and skipped seven checks whose inputs
were unavailable. The dedicated payload verifier, PMGR fault-injection test,
and pinned-source audit also passed.

No valid GFX power request, GPC or GPU-core register access, firmware upload,
or rendering workload was performed during the unattended period. A real
power-on could still hang the device; force-restart recovery from that specific
failure and the electrical behavior of the transition remain unproven. The
next hardware step is an operator-present, separately reviewed power-only
run using the persisted host checkpoint, followed by a restart and control
boot; do not advance to the GPU ID read or firmware on a failed or uncertain
transition.
