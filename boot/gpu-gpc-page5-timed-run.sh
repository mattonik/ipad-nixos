#!/bin/sh
# Run the existing one-shot page-5 module after GPC poll in the cycle payload.
set -u
[ "$#" -eq 2 ] || exit 2
hash=$1 boot_id=$2
case "$boot_id" in ????????-????-????-????-????????????) ;; *) exit 2 ;; esac
[ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot_id" ] || exit 1
case "$hash" in *[!0-9a-f]*|'') exit 2 ;; esac
[ "${#hash}" -eq 64 ] || exit 2
[ "$(sha256sum /tmp/gpu-gpc-page5-timed | cut -d ' ' -f 1)" = "$hash" ] || exit 1
[ "$(sha256sum /tmp/j81-page5-read-once.ko | cut -d ' ' -f 1)" = ca16576e6d574ff3587d631cd3fb82e3ae0ce83f49cdd5c4d3156f9306099e4c ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek | cut -d ' ' -f 1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
[ "$(sha256sum /sys/module/gpu_pmgr_cycle/notes/.note.gnu.build-id | cut -d ' ' -f 1)" = 8e4e9917c1607b351aa9d9a087c571b9aff353baf6fec3f7e3cbae7fb12e4ac6 ] || exit 1
[ "$(cat /proc/device-tree/model)" = 'Apple iPad Air 2 (Wi-Fi)' ] || exit 1
tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,j81 || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_status)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_usage)" = 1 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
[ ! -e /tmp/gpu-gpc-page5-timed.once ] || exit 1
[ ! -e /tmp/gpu-gpc-init.once ] || exit 1
[ ! -e /tmp/j81-page5-read-once.once ] || exit 1
[ ! -e /sys/module/page5_read_once ] || exit 1
/tmp/gpu-pmgr-peek || exit 1
mkdir /tmp/j81-page5-read-once.once || exit 1
/sbin/insmod /tmp/j81-page5-read-once.ko offset=4 || exit 1
[ -r /sys/devices/j81-page5-read-once/read_once ] || exit 1
exec /tmp/gpu-gpc-page5-timed
