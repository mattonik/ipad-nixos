#!/bin/sh
# Wrapper for gpu-watchdog-supervisor --core-revision-cycle in the MiscACG experiment: pin the reader and the observer kernel, then run it.
set -u
[ "$#" -eq 1 ] || exit 2
hash=$1
case "$hash" in [0-9a-f][0-9a-f]*) ;; *) exit 2 ;; esac
[ "$(sha256sum /tmp/gpu-core-id-gated | cut -d ' ' -f 1)" = "$hash" ] || exit 1
[ "$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)" = a2dda2719fef771c109dd2ca2baee4bdc31ec13902aed677f4ea7d9aad7b7f4a ] || exit 1
grep -q '^rootfs / rootfs ' /proc/mounts || exit 1
if grep -q '^/dev/' /proc/mounts; then exit 1; fi
exec /tmp/gpu-core-id-gated
