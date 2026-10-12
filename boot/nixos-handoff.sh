#!/bin/sh
# Stage-1 hand-off from the debug initramfs to a NixOS system that lives in RAM (docs/plans/2026-10-11-nixos-in-ram.md, "B-prime").
#
# It must run as PID 1 (busybox switch_root refuses otherwise), so the debug hook SOURCES this file (`. /usr/bin/nixos-handoff; nixos_handoff`) after USB networking is up.
# Executed directly (tests, manual runs) it calls nixos_handoff itself. It only acts when the kernel command line carries
#   j81.nixos=http://172.16.42.2:8000/
# which names a directory on the Mac that serves `root.squashfs` (the Nix store of the NixOS system, zstd) and `toplevel` (one line: the store path of the system).
# On ANY failure it logs, undoes what it mounted, and RETURNS 1, so the telnet/SSH recovery shell of the debug initramfs stays available. On success it never returns
# (switch_root replaces PID 1).
#
# Steps: fetch the squashfs into a tmpfs, loop-mount it, put a writable overlay over the store, copy the private overlay files that are already in this initramfs
# (firmware, Wi-Fi network, ssh keys) into the new root, then switch_root into the NixOS stage 2.
#
# Overridable for tests: CMDLINE, WORK (default /nixos-handoff), LOG, TIMEOUT_SECS, DRY_RUN=1 (stop before switch_root, clean up, return 0), HOOK=script (with DRY_RUN: run it
# with the new root and the toplevel before cleaning up).
CMDLINE=${CMDLINE:-/proc/cmdline}
WORK=${WORK:-/nixos-handoff}
LOG=${LOG:-/var/log/nixos-handoff.log}
TIMEOUT_SECS=${TIMEOUT_SECS:-120}

nh_say() { echo "nixos-handoff: $*" | tee -a "$LOG" >&2; }

nh_cleanup() {
	umount "$WORK/newroot/nix/store" 2>/dev/null
	umount "$WORK/newroot" 2>/dev/null
	umount "$WORK/ro" 2>/dev/null
	[ -n "$(cat "$WORK/loopdev" 2>/dev/null)" ] && losetup -d "$(cat "$WORK/loopdev")" 2>/dev/null
	umount "$WORK" 2>/dev/null
	rmdir "$WORK" 2>/dev/null
}

# Everything up to (not including) switch_root, in a subshell so `exit` can be used for failures; mounts are system-wide and survive it.
nh_prepare() {
	url=$1
	nh_fail() { nh_say "FAILED: $*; staying in the debug initramfs"; nh_cleanup; exit 1; }

	# 1. wait for the server (USB networking just came up; the Mac may need a few seconds)
	t=0
	until wget -q -T 3 -O /dev/null "${url}toplevel" 2>/dev/null; do
		t=$((t + 3))
		[ "$t" -ge "$TIMEOUT_SECS" ] && nh_fail "no answer from ${url}toplevel after ${TIMEOUT_SECS}s"
		sleep 3
	done
	nh_say "server answers"

	# 2. fetch into a tmpfs (RAM; the squashfs file stays there, the pages of its store are decompressed on demand)
	mkdir -p "$WORK" || nh_fail "cannot create $WORK"
	mount -t tmpfs -o size=900m tmpfs "$WORK" || nh_fail "tmpfs for the download"
	toplevel=$(wget -q -T 10 -O - "${url}toplevel" | head -n 1)
	case "$toplevel" in /nix/store/*) ;; *) nh_fail "bad toplevel '$toplevel'" ;; esac
	nh_say "toplevel $toplevel"
	echo "$toplevel" > "$WORK/toplevel"
	wget -q -T 30 -O "$WORK/root.squashfs" "${url}root.squashfs" || nh_fail "download of root.squashfs"
	nh_say "downloaded $(wc -c < "$WORK/root.squashfs") bytes"

	# 3. loop-mount the squashfs read-only
	mkdir -p "$WORK/ro" "$WORK/newroot" "$WORK/upper" "$WORK/work"
	# busybox losetup has no --show: take the next free device, then attach read-only
	loopdev=$(losetup -f) && losetup -r "$loopdev" "$WORK/root.squashfs" || nh_fail "losetup"
	echo "$loopdev" > "$WORK/loopdev"
	mount -t squashfs -o ro "$loopdev" "$WORK/ro" || nh_fail "mount squashfs (kernel needs SQUASHFS and SQUASHFS_ZSTD)"
	# netboot squashfs layout (nixpkgs make-squashfs): every store path is a directory at the top of the image, next to `nix-path-registration`
	STOREDIR="$WORK/ro"
	[ -e "$STOREDIR/${toplevel#/nix/store/}/init" ] || nh_fail "the system's init is not in the squashfs"

	# 4. new root: a tmpfs with /nix/store = overlay(lower = squashfs store, upper = tmpfs)
	mount -t tmpfs -o size=256m tmpfs "$WORK/newroot" || nh_fail "tmpfs for the new root"
	mkdir -p "$WORK/newroot/nix/store" "$WORK/newroot/proc" "$WORK/newroot/sys" "$WORK/newroot/dev" "$WORK/newroot/run" "$WORK/newroot/tmp" \
		"$WORK/newroot/etc" "$WORK/newroot/root" "$WORK/newroot/var" "$WORK/newroot/lib" "$WORK/newroot/bin" "$WORK/newroot/usr"
	mount -t overlay overlay -o "lowerdir=$STOREDIR,upperdir=$WORK/upper,workdir=$WORK/work" "$WORK/newroot/nix/store" || nh_fail "overlay on the store (kernel needs OVERLAY_FS)"

	# 5. private and boot-time files from this initramfs into the new root (never from the network)
	[ -d /lib/firmware ] && { mkdir -p "$WORK/newroot/lib/firmware"; cp -a /lib/firmware/. "$WORK/newroot/lib/firmware/" 2>/dev/null; }
	[ -d /root/.ssh ] && { mkdir -p "$WORK/newroot/root/.ssh"; cp -a /root/.ssh/. "$WORK/newroot/root/.ssh/" 2>/dev/null; chmod 700 "$WORK/newroot/root" "$WORK/newroot/root/.ssh"; }
	[ -d /etc/wifi ] && { mkdir -p "$WORK/newroot/etc/wifi"; cp -a /etc/wifi/. "$WORK/newroot/etc/wifi/" 2>/dev/null; }
	[ -f /etc/wpa_supplicant.conf ] && cp -a /etc/wpa_supplicant.conf "$WORK/newroot/etc/wpa_supplicant.conf"
	printf '%s\n' "$toplevel" > "$WORK/newroot/etc/j81-toplevel"
	exit 0
}

nixos_handoff() {
	nh_url=
	for nh_w in $(cat "$CMDLINE" 2>/dev/null); do
		case "$nh_w" in j81.nixos=*) nh_url=${nh_w#j81.nixos=} ;; esac
	done
	[ -n "$nh_url" ] || return 0	# not requested: the normal debug flow continues
	case "$nh_url" in */) ;; *) nh_url="$nh_url/" ;; esac
	mkdir -p "$(dirname "$LOG")"
	nh_say "requested: $nh_url"

	( nh_prepare "$nh_url" ) || return 1

	nh_top=$(cat "$WORK/toplevel")
	if [ "$DRY_RUN" = 1 ]; then
		nh_say "DRY_RUN: everything mounted ($(ls "$WORK/ro" | wc -l) store paths); cleaning up without switching"
		# HOOK=script: run it with the new root and the toplevel while everything is still mounted (live checks, e.g. a chroot)
		[ -n "$HOOK" ] && sh "$HOOK" "$WORK/newroot" "$nh_top"
		nh_cleanup
		return 0
	fi
	nh_say "switching root to $nh_top/init"
	# Stop the debug services that hold the old root; the NixOS system brings its own sshd and networking.
	killall telnetd dropbear udhcpd wpa_supplicant udhcpc 2>/dev/null
	exec switch_root "$WORK/newroot" "$nh_top/init"
	nh_say "switch_root did not take over"
	nh_cleanup
	return 1
}

# Executed directly (tests, manual runs): run it. Sourced by the init hook: only define the functions.
case "$0" in *nixos-handoff*) nixos_handoff; exit $? ;; esac
