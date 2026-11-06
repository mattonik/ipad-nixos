#!/bin/sh
# One PMGR off/on generation; no GPU MMIO. A failed cycle consumes the boot.
set -u
[ "$#" -eq 2 ] || exit 2
module_hash=$1
notes_hash=$2
case "$module_hash:$notes_hash" in
  [0-9a-f][0-9a-f]*:[0-9a-f][0-9a-f]*) ;;
  *) exit 2 ;;
esac
[ "$(sha256sum /tmp/gpu-pmgr-cycle.ko | cut -d ' ' -f 1)" = "$module_hash" ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = "$notes_hash" ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek | cut -d ' ' -f 1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
/sbin/insmod /tmp/gpu-pmgr-cycle.ko || exit 1
[ -w /sys/devices/gpu-pmgr-cycle/cycle_once ] || exit 1
/tmp/gpu-pmgr-peek || exit 1
printf 'stage=before-pmgr-cycle module=%s kernel_notes=%s\n' "$module_hash" "$notes_hash"
IFS= read -r reply || exit 1
[ "$reply" = CYCLE ] || exit 1
printf '1\n' > /sys/devices/gpu-pmgr-cycle/cycle_once
result=$?
printf 'stage=after-pmgr-cycle rc=%s\n' "$result"
exit "$result"
