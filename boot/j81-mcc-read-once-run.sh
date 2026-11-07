#!/bin/sh
# Guard all identity and RAM-boot conditions before module insertion.
set -u
[ "$#" -eq 4 ] || exit 2
mode=$1
shift
module_hash=$1
notes_hash=$2
boot_id=$3
for hash in "$module_hash" "$notes_hash"; do
    [ "${#hash}" -eq 64 ] || exit 2
    case "$hash" in *[!0-9a-f]*) exit 2 ;; esac
done
case "$boot_id" in ????????-????-????-????-????????????) ;; *) exit 2 ;; esac
[ "$(uname -r)" = 7.3.0-rc1 ] || exit 1
[ "$(uname -m)" = aarch64 ] || exit 1
[ "$notes_hash" = 82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014 ] || exit 1
[ "$(cat /proc/sys/kernel/random/boot_id)" = "$boot_id" ] || exit 1
[ "$(cat /proc/device-tree/model)" = "Apple iPad Air 2 (Wi-Fi)" ] || exit 1
tr '\000' '\n' </proc/device-tree/compatible | grep -qx apple,j81 || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = "$notes_hash" ] || exit 1
[ "$(sha256sum /tmp/j81-mcc-read-once.ko | cut -d ' ' -f 1)" = "$module_hash" ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
[ ! -e /tmp/j81-mcc-read-once.once ] || exit 1
[ ! -e /sys/module/mcc_read_once ] || exit 1
case "$mode" in
    --preflight) exit 0 ;;
    --run) ;;
    *) exit 2 ;;
esac
mkdir /tmp/j81-mcc-read-once.once || exit 1
/sbin/insmod /tmp/j81-mcc-read-once.ko || exit 1
[ -r /sys/devices/j81-mcc-read-once/read_once ] || exit 1
printf 'stage=before-mcc-read address=0x200000830 width=32\n'
IFS= read -r reply || exit 1
[ "$reply" = READ ] || exit 1
result=$(cat /sys/devices/j81-mcc-read-once/read_once) || exit 1
case "$result" in 'address=0x200000830 value=0x'????????) ;; *) exit 1 ;; esac
value=${result##*value=}
printf 'stage=after-mcc-read address=0x200000830 value=%s\n' "$value"
printf 'stage=finished rc=0\n'
