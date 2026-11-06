#!/bin/sh
# Post-PMGR-cycle Fender-only experiment. Never reads or writes RGX.
set -u
[ "$#" -eq 1 ] || exit 2
binary_hash=$1
case "$binary_hash" in [0-9a-f][0-9a-f]*) ;; *) exit 2 ;; esac
[ "$(sha256sum /tmp/gpu-fender-wake | cut -d ' ' -f 1)" = "$binary_hash" ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_status 2>/dev/null)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_usage 2>/dev/null)" = 1 ] || exit 1
exec /tmp/gpu-fender-wake
