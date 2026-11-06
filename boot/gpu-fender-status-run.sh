#!/bin/sh
# Read-only Fender status probe; no reset, wake, firmware, or RGX access.
set -u
[ "$#" -eq 1 ] || exit 2
module_hash=$1
case "$module_hash" in [0-9a-f][0-9a-f]*) ;; *) exit 2 ;; esac
[ "$(sha256sum /tmp/gpu-fender-status.ko | cut -d ' ' -f 1)" = "$module_hash" ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_status 2>/dev/null)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_usage 2>/dev/null)" = 1 ] || exit 1
if [ ! -d /sys/devices/gpu-fender-status ]; then /sbin/insmod /tmp/gpu-fender-status.ko || exit 1; fi
printf 'stage=before-fender-status module=%s\n' "$module_hash"
printf 'stage=state value='; cat /sys/devices/gpu-fender-status/state
printf 'stage=control value='; cat /sys/devices/gpu-fender-status/control
printf 'stage=hold value='; cat /sys/devices/gpu-fender-status/hold
printf 'stage=finished rc=0\n'
