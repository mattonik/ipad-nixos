#!/bin/sh
# Simulated MMIO only; uses a distinct executable and one-shot guard.
set -u
[ "$#" -eq 1 ] || exit 2
binary_hash=$1
[ "${#binary_hash}" -eq 64 ] || exit 2
case "$binary_hash" in *[!0-9a-f]*) exit 2 ;; esac
[ "$binary_hash" = 8ea9fbf71ecf19cf5f42c1b2548d35187ae8a89f82fb69d9626404402471359a ] || exit 1
[ "$(sha256sum /tmp/gpu-bridge-sim-live | cut -d ' ' -f 1)" = "$binary_hash" ] || exit 1
[ "$(sha256sum /tmp/gfx-bridge-plan.bin | cut -d ' ' -f 1)" = 1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435 ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek | cut -d ' ' -f 1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
[ "$(sha256sum /sys/module/gpu_pmgr_once/notes/.note.gnu.build-id | cut -d ' ' -f 1)" = b471f3c159c4d326ec466f78967dd5a57ecf1e6d3af9665b93f1ff4ba5f617fb ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-once/power/runtime_status)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-once/power/runtime_usage)" = 1 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
/tmp/gpu-pmgr-peek || exit 1
exec /tmp/gpu-bridge-sim-live
