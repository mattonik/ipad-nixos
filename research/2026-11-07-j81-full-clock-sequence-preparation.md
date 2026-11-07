# J81 full clock sequence preparation

Date: 2026-11-07

## Prepared offline

The staged sequence uses one `gpu-pmgr-cycle` payload from setup through the
final observation. The new `gpu-bridge-once-cycle-run.sh` applies the existing
full selector 9/10 table wrapper's pinned plan, binary, kernel-note, PMGR-peek,
RAM-rootfs, and runtime-active checks against the cycle payload. It does not
change the bridge probe or table. The watchdog supervisor now dispatches the
full-table, cycle GPC-init, and post-GPC probes under separate 20-second
watchdog sessions. Host captures require each checkpoint in order and record
the post-GPC bridge values without rejecting a difference from baseline.

The bundle is at
`artifacts/live/gpu-test-bundle-20261107-cycle-v2`; its manifest records each
input hash. It includes the pinned plan file because the full-table binary
requires `/tmp/gfx-bridge-plan.bin`. The supervisor was rebuilt from the
updated source through the existing Flake output
`packages.x86_64-linux.gpu-watchdog-supervisor-static` and staged separately
at `artifacts/live/gcroot-gpu-watchdog-supervisor-cycle`.

## Payload gate after the failed insert

The 2026-11-07 attempt used `gcroot-gpu-pmgr-once-payload`. Its DTB retains
`experimental,j81-gpu-test-no-poweroff`, while `gpu-pmgr-cycle.ko` deliberately
rejects that property and returns the init function's default `-EINVAL`. This
matches the observed `insmod: ... Invalid argument`; the PMGR cycle was not
started. Do not retry on that boot.

For a new boot, use exactly
`artifacts/live/gpu-pmgr-cycle/payload/m1n1-linux.bin` (SHA-256
`3dd234b5f20c85b71873a148463e5d6a682c232c1bdef9f5b5f3ea2d8ed96835`), paired
with `artifacts/live/gpu-pmgr-cycle/gpu-pmgr-cycle.ko` (SHA-256
`c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23`). The
payload DTB has the expected `apple,t7000-pmgr-pwrstate` GFX node at
`reg = <0x20320 0x4>` and omits the no-poweroff marker. Its kernel notes hash
is `82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`, which
is the hash passed to the capture command below.

Before staging or running any test wrapper after that boot, perform this
read-only live-DT preflight. Both checks must pass; stop if the guard file
exists or the provider compatible differs:

```sh
gfx=/sys/firmware/devicetree/base/soc/power-management@20e000000/power-controller@20320
test -r "$gfx/compatible" && tr '\0' '\n' < "$gfx/compatible" | grep -qx apple,t7000-pmgr-pwrstate
test ! -e "$gfx/experimental,j81-gpu-test-no-poweroff"
sha256sum /sys/kernel/notes
```

The notes digest must match the value above. These checks only read the live
device tree and kernel notes, before module insertion.

## Candidate operator sequence

These commands were prepared but not run against a device. Start with a fresh
RAM boot and stage the named inputs:

```sh
python3 boot/stage_gpu_test_bundle.py \
  --bundle artifacts/live/gpu-test-bundle-20261107-core-revision \
  bin/gpu-pmgr-peek bin/gpu-bridge-once bin/gpu-gpc-init \
  bin/gpu-bridge-postgpc bin/gpu-core-revision-once bin/gpu-watchdog-supervisor \
  modules/gpu-pmgr-cycle.ko data/gfx-bridge-plan.bin \
  wrappers/gpu-pmgr-cycle-run.sh wrappers/gpu-bridge-once-cycle-run.sh \
  wrappers/gpu-gpc-init-cycle-run.sh wrappers/gpu-bridge-postgpc-cycle-run.sh \
  wrappers/gpu-core-revision-once-cycle-run.sh
```

Run each capture once, in order, using separate exclusive log paths:

```sh
python3 boot/gpu_pmgr_cycle_capture.py \
  artifacts/live/gpu/clock-cycle-$(date +%Y%m%d-%H%M%S).log \
  c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23 \
  82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014

python3 boot/gpu_bridge_capture.py \
  artifacts/live/gpu/clock-table-$(date +%Y%m%d-%H%M%S).log \
  3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c \
  artifacts/live/gpu-test-bundle-20261107-core-revision/data/gfx-bridge-plan.bin \
  --supervised --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --cycle-payload --cycle-wrapper-sha256 7d483501cd269e4fe0f24098bc5e4f08fd7206505091e367baaea6162e59f281

python3 boot/gpu_gpc_init_capture.py \
  artifacts/live/gpu/gpc-init-$(date +%Y%m%d-%H%M%S).log \
  8a67ba955fca1aa2fe2b043e4512919aefa49c475542af1581d32b388f988282 \
  --supervised --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --wrapper-sha256 5c6ad81d26aa48d7361f9a47de9117abcc3e431b5ab7fe93fc8805732cf5ce1f

python3 boot/gpu_bridge_postgpc_capture.py \
  artifacts/live/gpu/postgpc-bridge-$(date +%Y%m%d-%H%M%S).log \
  b43aa32902eea641350715f5ad9dd6f3275a711877460135825c3409dcab2876 \
  --supervised --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --wrapper-sha256 894568995c6f196e23df65462d4ca97cd971d9a5ebbc4d15b4e2333db16a1cfd
```

The final bridge values are reported alongside the historical post-GPC
baseline (`+0x18 = 0x4`, `+0x1c = 0x10001`); a difference is the observation,
not a capture failure. An unexpected PMGR/GPC state, stage, timeout, missing
checkpoint, or incomplete capture stops the sequence. Do not retry in that
boot.

## Recovery limit

The watchdog supervisor stops feeding after an incomplete child stage and
fails closed. The 20-second hardware watchdog is only a reset contingency: no
test demonstrates recovery from a wedged MMIO/interconnect access or proves
the watchdog continues running through such a stall. After any failed or
incomplete stage, stop and re-establish a fresh PongoOS/Linux handoff before
another experiment. The post-GPC comparison is read-only; the full table and
GPC-init phases still have undocumented hardware effects and no rollback.

## Prepared single-read core-window comparison

The comparison is built and included in
`artifacts/live/gpu-test-bundle-20261107-core-revision`. It adds one
watchdog-supervised read of GPU revision at `0x201000020`, after exact PMGR
(`0x3ff`), GPC-state (`1`), and GPC-control (`0x40000000`) checks. It does not
read `0x201000018`, write GPU registers, or attempt firmware. The earlier ID
probe hung at this same revision address, so a hang remains possible. The
20-second watchdog is a contingency only; reset through a wedged
MMIO/interconnect read has not been established.

The host capture expects two PMGR read checkpoints: the cycle wrapper's
`gpu-pmgr-peek` preflight (raw value plus decoded fields), then the probe's
own raw PMGR gate before GPC state/control and the single revision read.

The built inputs are pinned by these SHA-256 values:

| Input | SHA-256 |
| --- | --- |
| Probe | `2dbaa48a8683a3164fd69b1d43aaeb518e81d66d0b942170196893a023e1f1b3` |
| Watchdog supervisor | `093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f` |
| Cycle wrapper | `55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09` |

For a fresh RAM boot using the cycle payload, first run the read-only live-DT
preflight above. Stage the exact run inputs (staging only; it does not execute
the probes):

```sh
python3 boot/stage_gpu_test_bundle.py \
  --bundle artifacts/live/gpu-test-bundle-20261107-core-revision \
  bin/gpu-pmgr-peek bin/gpu-bridge-once bin/gpu-gpc-init \
  bin/gpu-bridge-postgpc bin/gpu-core-revision-once bin/gpu-watchdog-supervisor \
  modules/gpu-pmgr-cycle.ko data/gfx-bridge-plan.bin \
  wrappers/gpu-pmgr-cycle-run.sh wrappers/gpu-bridge-once-cycle-run.sh \
  wrappers/gpu-gpc-init-cycle-run.sh wrappers/gpu-bridge-postgpc-cycle-run.sh \
  wrappers/gpu-core-revision-once-cycle-run.sh
```

Run the four existing candidate steps above in order, then make the new
one-read comparison the final command, only if every prior capture completes
and the same boot remains responsive:

```sh
python3 boot/gpu_core_revision_capture.py \
  artifacts/live/gpu/core-revision-$(date +%Y%m%d-%H%M%S).log \
  2dbaa48a8683a3164fd69b1d43aaeb518e81d66d0b942170196893a023e1f1b3 \
  --supervisor-sha256 093ee6ab9454f402553e1c8ce2d06f7e16170d19b2db7494518ae0c279234c3f \
  --wrapper-sha256 55620440940c227ddb2e28625e90d965af34eea855df3e3c7da0208448420f09
```

Any failed gate, incomplete log, lost shell, or watchdog reset ends the run:
do not retry in that boot; recover through a fresh PongoOS/Linux handoff or
normal restart/DFU. No hardware staging or execution was performed while
preparing this path.

## Offline checks

The cycle-mode host capture simulations pass for the full 66-pair plan, GPC
init checkpoints, and post-GPC read stages with changed bridge values. The
bundle contract verifies the plan hash and staged manifests. The updated ARM64
watchdog supervisor builds through the Flake output. No device, RAM staging,
or hardware capture was used.
