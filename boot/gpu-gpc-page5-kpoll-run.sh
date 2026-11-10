#!/bin/sh
# Guard the cycle-payload boot, then run the one-shot in-kernel GPC/page-5 batch.
set -u
[ "$#" -eq 3 ] || exit 2
hash=$1 boot_id=$2 mode=$3
case "$mode" in immediate|paired|delayed) ;; *) exit 2 ;; esac
case "$boot_id" in ????????-????-????-????-????????????) ;; *) exit 2 ;; esac
case "$hash" in *[!0-9a-f]*|'') exit 2 ;; esac
[ "${#hash}" -eq 64 ] || exit 2
dev=/sys/devices/j81-gpc-page5-kpoll
[ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot_id" ] || exit 1
[ "$(uname -r)" = 7.3.0-rc1 ] || exit 1
[ "$(uname -m)" = aarch64 ] || exit 1
[ "$(sha256sum /tmp/j81-gpc-page5-kpoll.ko | cut -d ' ' -f 1)" = "$hash" ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek | cut -d ' ' -f 1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
[ "$(sha256sum /sys/module/gpu_pmgr_cycle/notes/.note.gnu.build-id | cut -d ' ' -f 1)" = 8e4e9917c1607b351aa9d9a087c571b9aff353baf6fec3f7e3cbae7fb12e4ac6 ] || exit 1
[ "$(cat /proc/device-tree/model)" = 'Apple iPad Air 2 (Wi-Fi)' ] || exit 1
tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,j81 || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_status)" = active ] || exit 1
[ "$(cat /sys/devices/gpu-pmgr-cycle/power/runtime_usage)" = 1 ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
for once in gpu-gpc-page5-kpoll gpu-gpc-page5-timed gpu-gpc-init gpu-gpc-timed-revision j81-page5-read-once; do
    [ ! -e "/tmp/$once.once" ] || exit 1
done
[ ! -e /sys/module/page5_read_once ] || exit 1
[ ! -e /sys/module/gpc_page5_kpoll ] || exit 1
/tmp/gpu-pmgr-peek || exit 1
mkdir /tmp/gpu-gpc-page5-kpoll.once || exit 1
/sbin/insmod /tmp/j81-gpc-page5-kpoll.ko "mode=$mode" || exit 1
# --- host-acknowledged protocol (boot/test_gpu_gpc_page5_kpoll_run.py runs from here) ---
[ -r "$dev/gpc_state" ] && [ -r "$dev/batch" ] || exit 1
printf 'stage=before-gpc-state address=0x201e01000 width=32\n'
IFS= read -r reply || exit 1
[ "$reply" = READ ] || exit 1
result=$(cat "$dev/gpc_state") || exit 1
case "$result" in 'address=0x201e01000 value=0x'????????) ;; *) exit 1 ;; esac
printf 'stage=after-gpc-state raw=%s\n' "${result#*value=}"
if [ "$result" != 'address=0x201e01000 value=0x00000000' ]; then
    printf 'stage=finished rc=1\n'
    exit 1
fi
# The host acknowledges this line before the irreversible batch starts.
printf 'stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=%s\n' "$mode"
IFS= read -r reply || exit 1
[ "$reply" = READ ] || exit 1
# Nothing is reported between this marker and the end of the kernel batch.
printf 'checkpoint=before-kernel-batch\n'
if ! result=$(cat "$dev/batch"); then
    printf 'checkpoint=kernel-batch-read-failed\nstage=finished rc=1\n'
    exit 1
fi
printf 'checkpoint=kernel-batch %s\n' "$result"
case "$result" in
    "result=ok mode=$mode raw=0x"*) ;;
    *) printf 'stage=finished rc=1\n'; exit 1 ;;
esac
printf 'stage=after-gpc-page5-kpoll %s\n' "$result"
printf 'stage=finished rc=0\n'
