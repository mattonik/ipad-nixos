#!/bin/sh
# Manage the macOS Linux-builder VM that every Linux build in this repo depends on (kernel, NixOS image, static tools). Runbook: docs/build-infrastructure.md.
#
#   tools/builder.sh status                         is it running? (vzvm process, SSH port 31022, a login with keys/builder_ed25519)
#   tools/builder.sh start                          build the launcher if needed and start the VM IN THE BACKGROUND from the state directory (the VM's disk lives there)
#   tools/builder.sh stop                           sync in the guest, then SIGTERM vzvm (clean guest shutdown in ~30-90 s). Never SIGKILLs unless FORCE=1.
#   tools/builder.sh archive [-n] [--delete-local [--yes]]
#                                                   copy the VM's state to the NAS as cold storage (see below); -n = dry run
#   tools/builder.sh restore [-n] [--from DIR] [--to DIR] [--force]
#                                                   bring an archive back to a LOCAL directory and make it ready for `start`
#
# State directory: $BUILDER_DIR (default: the repository root). It holds nixos.qcow2 (the VM's disk, 40 GB sparse, ~16 GB used), store-*.img (derived, rebuilt by the launcher),
# vzvm.json (generated at each launch), keys/ and result-linux-builder (the launcher, a GC root).
# Archive base: $BUILDER_ARCHIVE (default /Volumes/martin/Projects/Archive/ipad-nixos), one timestamped directory per archive plus a `latest` pointer.
# An archive holds: nixos.qcow2.zst (zstd), keys.tgz, vzvm.json, a self-contained Nix file cache of the HOST-side closure the VM needs (the launcher and the guest kernel/initrd, so
# a restore does not depend on cache.nixos.org still serving them), meta.txt and SHA256SUMS. The VM is never run from the NAS: network storage is too slow and unsafe for it.
#
# Never run a bare `nix run nixpkgs#darwin.linux-builder-vz`: it creates a different, empty VM in the current directory.
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
STATE=${BUILDER_DIR:-$REPO}
ARCH=${BUILDER_ARCHIVE:-/Volumes/martin/Projects/Archive/ipad-nixos}
PYTHON=${PYTHON:-/opt/homebrew/bin/python3}
NIX="nix --extra-experimental-features nix-command"
KEY="$STATE/keys/builder_ed25519"
SSH="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=4 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR -p 31022 builder@localhost"

say() { echo "builder: $*"; }
die() { echo "builder: $*" >&2; exit 1; }
vzvm_pid() { pgrep -f "bin/vzvm $STATE/vzvm.json" | head -n 1; }
size_of() { stat -f %z "$1" 2>/dev/null || echo 0; }
used_of() { du -k "$1" 2>/dev/null | awk '{print $1 * 1024}'; }   # bytes actually used (qcow2 is sparse)
free_kb() { df -k "$1" 2>/dev/null | awk 'NR==2 {print $4}'; }
human() { awk -v b="$1" 'BEGIN { printf "%.1f GB", b / 1073741824 }'; }
need_stopped() { [ -z "$(vzvm_pid)" ] || die "the builder is running (pid $(vzvm_pid)); stop it first: tools/builder.sh stop"; }
no_nix_build() { [ "${BUILDER_TEST:-0}" = 1 ] && return 0; pgrep -f "nix build|nix-build|nix-store --realise" >/dev/null 2>&1 && die "a nix build seems to be running; finish it first"; return 0; }
json_get() { "$PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d[sys.argv[2]])' "$1" "$2"; }
guest_system() { dirname "$(json_get "$STATE/vzvm.json" kernel)"; }
launcher_path() { readlink -f "$STATE/result-linux-builder"; }

# Is DIR on network storage (smbfs, nfs, afpfs, webdav)? The VM disk must not run from there.
on_network_fs() {
	mp=$(df "$1" 2>/dev/null | awk 'NR==2 {print $NF}')
	mount | grep -E " on $mp \((smbfs|nfs|afpfs|webdav)" >/dev/null 2>&1
}

cmd_status() {
	pid=$(vzvm_pid)
	[ -n "$pid" ] && echo "vzvm: running (pid $pid)" || echo "vzvm: not running"
	if lsof -nP -iTCP:31022 -sTCP:LISTEN >/dev/null 2>&1; then echo "ssh port 31022: listening"; else echo "ssh port 31022: closed"; fi
	if $SSH true 2>/dev/null; then echo "login as builder: ok"; else echo "login as builder: failed (expected while stopped or still booting)"; fi
	[ -f "$STATE/nixos.qcow2" ] && echo "disk: $STATE/nixos.qcow2 ($(human "$(used_of "$STATE/nixos.qcow2")") used)" || echo "disk: none in $STATE (archived? see: tools/builder.sh restore)"
}

cmd_start() {
	[ -z "$(vzvm_pid)" ] || { echo "already running"; exit 0; }
	[ -f "$STATE/nixos.qcow2" ] || echo "note: no nixos.qcow2 in $STATE: the launcher will create a fresh EMPTY VM (restore the archive first if you want the old one)"
	cd "$STATE" || exit 1
	[ -x result-linux-builder/bin/create-builder ] || $NIX build "$REPO#packages.aarch64-darwin.linux-builder" -o result-linux-builder || exit 1
	# from INSIDE the state directory: the disk (nixos.qcow2, store-*.img, vzvm.json, keys/) is found relative to the working directory
	nohup ./result-linux-builder/bin/create-builder > "$STATE/builder.log" 2>&1 &
	echo "started (log: $STATE/builder.log); waiting for the guest to accept logins..."
	n=0
	until $SSH true 2>/dev/null; do n=$((n + 1)); [ "$n" -ge 40 ] && { echo "not up after ~2 min: see $STATE/builder.log"; exit 1; }; sleep 3; done
	echo "builder is up"
}

cmd_stop() {
	pid=$(vzvm_pid)
	[ -n "$pid" ] || { echo "not running"; exit 0; }
	no_nix_build
	$SSH sync 2>/dev/null
	kill -TERM "$pid"
	n=0
	while kill -0 "$pid" 2>/dev/null; do
		n=$((n + 1))
		if [ "$n" -ge 45 ]; then
			[ "${FORCE:-0}" = 1 ] && { kill -KILL "$pid"; echo "force-killed"; break; }
			echo "still running after ~90 s; wait longer or use FORCE=1 (risky)"; exit 1
		fi
		sleep 2
	done
	echo "stopped"
}

cmd_archive() {
	dry=0; del=0; yes=0
	for a in "$@"; do case "$a" in -n) dry=1 ;; --delete-local) del=1 ;; --yes) yes=1 ;; *) die "unknown option $a" ;; esac; done
	need_stopped; no_nix_build
	[ -f "$STATE/nixos.qcow2" ] || die "no nixos.qcow2 in $STATE: nothing to archive"
	[ -f "$STATE/vzvm.json" ] || die "no vzvm.json in $STATE: start the VM once so the launcher writes it (it names the guest system the archive must contain)"
	[ -e "$STATE/result-linux-builder" ] || die "no result-linux-builder in $STATE (the launcher link)"
	launcher=$(launcher_path); guest=$(guest_system)
	[ -e "$launcher" ] && [ -e "$guest" ] || die "the launcher or guest system is missing from the Nix store ($launcher, $guest)"
	used=$(used_of "$STATE/nixos.qcow2")
	stamp=$(date +%Y%m%d-%H%M%S); dest="$ARCH/linux-builder-$stamp"
	say "archive plan"
	echo "  state directory:   $STATE"
	echo "  disk:              $STATE/nixos.qcow2  ($(human "$used") used of $(human "$(size_of "$STATE/nixos.qcow2")") apparent)"
	echo "  launcher:          $launcher"
	echo "  guest system:      $guest"
	echo "  destination:       $dest"
	echo "  NAS free space:    $( [ -d "$ARCH" ] && human $(( $(free_kb "$ARCH") * 1024 )) || echo '(directory missing)')"
	[ "$del" = 1 ] && echo "  afterwards:        DELETE the local nixos.qcow2 and store-*.img (after the archive verifies)"
	[ "$dry" = 1 ] && { say "dry run: nothing written"; exit 0; }
	mkdir -p "$ARCH" || die "cannot create $ARCH (is the NAS mounted?)"
	[ -w "$ARCH" ] || die "$ARCH is not writable"
	[ "$(free_kb "$ARCH")" -gt $(( used / 1024 + 4194304 )) ] || die "not enough free space on the NAS"
	mkdir "$dest" || die "cannot create $dest"

	say "1/5 compressing the disk (zstd) -> $dest/nixos.qcow2.zst"
	zstd -T0 -3 -q -f -o "$dest/nixos.qcow2.zst" "$STATE/nixos.qcow2" || die "zstd failed"
	say "2/5 hashing the source disk (for the restore check)"
	src_hash=$(shasum -a 256 "$STATE/nixos.qcow2" | awk '{print $1}')
	say "3/5 keys, launch config"
	tar -C "$STATE" -czf "$dest/keys.tgz" keys 2>/dev/null || die "tar of keys failed"
	cp "$STATE/vzvm.json" "$dest/vzvm.json"
	say "4/5 exporting the host-side closure (launcher and guest system) as a Nix file cache"
	$NIX copy --to "file://$dest/cache" "$launcher" "$guest" || die "nix copy failed"
	{
		echo "created: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
		echo "host: $(hostname)"
		echo "state_dir_at_archive_time: $STATE"
		echo "disk_apparent_bytes: $(size_of "$STATE/nixos.qcow2")"
		echo "disk_used_bytes: $used"
		echo "disk_sha256: $src_hash"
		echo "launcher: $launcher"
		echo "guest_system: $guest"
		echo "flake_lock_sha256: $(shasum -a 256 "$REPO/flake.lock" | awk '{print $1}')"
		echo "nix: $(nix --version 2>/dev/null)"
	} > "$dest/meta.txt"
	cp "$0" "$dest/builder.sh.copy" 2>/dev/null
	say "5/5 checksums and read-back verification (this reads everything back from the NAS)"
	( cd "$dest" && find . -type f ! -name SHA256SUMS -print0 | xargs -0 shasum -a 256 > SHA256SUMS && shasum -a 256 -c SHA256SUMS >/dev/null ) || die "verification FAILED: $dest is not trustworthy; nothing was deleted"
	zstd -t -q "$dest/nixos.qcow2.zst" || die "the compressed disk does not test clean; nothing was deleted"
	echo "$stamp" > "$ARCH/latest"; echo "linux-builder-$stamp" > "$ARCH/latest"
	say "archive verified: $dest ($(du -sh "$dest" | awk '{print $1}'))"

	if [ "$del" = 1 ]; then
		if [ "$yes" != 1 ]; then
			printf "builder: type 'delete' to remove the local VM disk (%s) and store image(s): " "$(human "$used")"
			read -r ans < /dev/tty 2>/dev/null || ans=""
			[ "$ans" = delete ] || { say "not deleted"; exit 0; }
		fi
		rm -f "$STATE/nixos.qcow2" "$STATE"/store-*.img "$STATE/builder.log"
		say "deleted the local disk and store image. Restore with: tools/builder.sh restore"
	else
		say "local files kept. Free the space later with: tools/builder.sh archive --delete-local  (a new archive) or delete $STATE/nixos.qcow2 yourself after checking the archive"
	fi
}

cmd_restore() {
	dry=0; force=0; from=""; to="$STATE"
	while [ $# -gt 0 ]; do
		case "$1" in -n) dry=1; shift ;; --force) force=1; shift ;; --from) from=$2; shift 2 ;; --to) to=$2; shift 2 ;; *) die "unknown option $1" ;; esac
	done
	need_stopped
	if [ -z "$from" ]; then
		[ -f "$ARCH/latest" ] || die "no archive found ($ARCH/latest missing); pass --from DIR"
		from="$ARCH/$(cat "$ARCH/latest")"
	fi
	[ -f "$from/meta.txt" ] && [ -f "$from/nixos.qcow2.zst" ] || die "$from is not a builder archive"
	mkdir -p "$to"
	meta() { sed -n "s/^$1: //p" "$from/meta.txt" | head -n 1; }
	used=$(meta disk_used_bytes); launcher=$(meta launcher); guest=$(meta guest_system)
	say "restore plan"
	echo "  archive:     $from  (created $(meta created))"
	echo "  target:      $to"
	echo "  disk:        $(human "$used") used; needs that much free space plus 4 GB; free now: $(human $(( $(free_kb "$to") * 1024 )))"
	echo "  store paths: $launcher and $guest (imported only if missing from the local Nix store)"
	on_network_fs "$to" && [ "${FORCE_NETWORK:-0}" != 1 ] && die "$to is on network storage; the VM disk must live on a local disk (FORCE_NETWORK=1 to override at your own risk)"
	[ -e "$to/nixos.qcow2" ] && [ "$force" != 1 ] && die "$to/nixos.qcow2 already exists; use --force to overwrite it"
	[ "$(free_kb "$to")" -gt $(( used / 1024 + 4194304 )) ] || die "not enough free space in $to"
	[ "$dry" = 1 ] && { say "dry run: nothing written"; exit 0; }

	say "1/4 verifying the archive checksums"
	( cd "$from" && shasum -a 256 -c SHA256SUMS >/dev/null ) || die "the archive does not verify; refusing to restore from it"
	say "2/4 decompressing the disk -> $to/nixos.qcow2"
	zstd -d -q -f --sparse -o "$to/nixos.qcow2" "$from/nixos.qcow2.zst" || die "decompression failed"
	[ "$(shasum -a 256 "$to/nixos.qcow2" | awk '{print $1}')" = "$(meta disk_sha256)" ] || die "the restored disk does not match the hash recorded at archive time"
	say "3/4 keys"
	[ -d "$to/keys" ] || tar -C "$to" -xzf "$from/keys.tgz"
	say "4/4 host-side closure"
	missing=""
	for p in "$launcher" "$guest"; do [ -e "$p" ] || missing="$missing $p"; done
	if [ -n "$missing" ]; then
		$NIX copy --from "file://$from/cache" --no-check-sigs $missing 2>/dev/null || {
			echo "builder: the import needs a trusted Nix user. Run this once, then run the restore again:" >&2
			echo "  sudo nix --extra-experimental-features nix-command copy --from file://$from/cache --no-check-sigs$missing" >&2
			exit 1
		}
	fi
	$NIX build "$launcher" -o "$to/result-linux-builder" >/dev/null 2>&1 || ln -sfn "$launcher" "$to/result-linux-builder"
	say "restored. Start it with:  BUILDER_DIR=$to tools/builder.sh start"
}

case "${1:-status}" in
status) cmd_status ;;
start) cmd_start ;;
stop) cmd_stop ;;
archive) shift; cmd_archive "$@" ;;
restore) shift; cmd_restore "$@" ;;
*) echo "usage: $0 status|start|stop|archive [-n] [--delete-local [--yes]]|restore [-n] [--from DIR] [--to DIR] [--force]" >&2; exit 2 ;;
esac
