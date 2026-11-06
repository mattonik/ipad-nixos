#!/bin/sh
set -u
[ "$#" -eq 1 ] || exit 2
[ "${#1}" -eq 64 ] || exit 2
case "$1" in *[!0-9a-f]*) exit 2;; esac
[ "$(sha256sum /tmp/gpu-bridge-segment|cut -d ' ' -f1)" = "$1" ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek|cut -d ' ' -f1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-once/power/runtime_status)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-once/power/runtime_usage)" = 1 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
grep -q '^/dev/' /proc/mounts && exit 1 || :
/tmp/gpu-pmgr-peek || exit 1
exec /tmp/gpu-bridge-segment
