#!/bin/sh
# A failed or blocked transition leaves unknown hardware state; never retry.
set -u
[ "$#" -eq 2 ] || exit 2
module_hash=$1
notes_hash=$2
for hash in "$module_hash" "$notes_hash"; do
    [ "${#hash}" -eq 64 ] || exit 2
    case "$hash" in *[!0-9a-f]*) exit 2 ;; esac
done
[ "$(sha256sum /tmp/gpu-pmgr-once.ko | cut -d ' ' -f 1)" = "$module_hash" ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = "$notes_hash" ] || exit 1
[ "$(sha256sum /tmp/gpu-pmgr-peek | cut -d ' ' -f 1)" = 78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd ] || exit 1
if [ -d /sys/module/gpu_pmgr_once ]; then
    # shortcut: reuse is restricted to the module verified on this boot; update after a reviewed rebuild.
    [ "$module_hash" = 39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89 ] || exit 1
    [ "$(sha256sum /sys/module/gpu_pmgr_once/notes/.note.gnu.build-id | cut -d ' ' -f 1)" = b471f3c159c4d326ec466f78967dd5a57ecf1e6d3af9665b93f1ff4ba5f617fb ] || exit 1
else
    /sbin/insmod /tmp/gpu-pmgr-once.ko || exit 1
fi
[ -w /sys/devices/gpu-pmgr-once/power_once ] || exit 1
/tmp/gpu-pmgr-peek || exit 1
printf 'stage=before-gfx-power module=%s kernel_notes=%s\n' "$module_hash" "$notes_hash"
IFS= read -r reply || exit 1
[ "$reply" = POWER ] || exit 1
printf '1\n' > /sys/devices/gpu-pmgr-once/power_once
result=$?
printf 'stage=after-gfx-power rc=%s\n' "$result"
exit "$result"
