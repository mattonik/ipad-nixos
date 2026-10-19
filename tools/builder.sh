#!/bin/sh
# Start, stop or query the macOS Linux-builder VM that every Linux build in this repo depends on (kernel, NixOS image, static tools). Runbook: docs/build-infrastructure.md.
#
#   tools/builder.sh status     is it running? (checks the vzvm process, the SSH port 31022 and a login with keys/builder_ed25519)
#   tools/builder.sh start      build the launcher if needed and start the VM IN THE BACKGROUND from inside the repo (the VM's disk lives in the repo directory)
#   tools/builder.sh stop       sync in the guest, then SIGTERM vzvm (clean guest shutdown in ~30-90 s). Never SIGKILLs unless FORCE=1.
#
# Never run a bare `nix run nixpkgs#darwin.linux-builder-vz`: it creates a different, empty VM in the current directory.
set -u
REPO=$(cd "$(dirname "$0")/.." && pwd)
KEY="$REPO/keys/builder_ed25519"
SSH="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=4 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR -p 31022 builder@localhost"

vzvm_pid() { pgrep -f "bin/vzvm $REPO/vzvm.json" | head -n 1; }

case "${1:-status}" in
status)
	pid=$(vzvm_pid)
	[ -n "$pid" ] && echo "vzvm: running (pid $pid)" || echo "vzvm: not running"
	if lsof -nP -iTCP:31022 -sTCP:LISTEN >/dev/null 2>&1; then echo "ssh port 31022: listening"; else echo "ssh port 31022: closed"; fi
	if $SSH true 2>/dev/null; then echo "login as builder: ok"; else echo "login as builder: failed (expected while stopped or still booting)"; fi
	;;
start)
	if [ -n "$(vzvm_pid)" ]; then echo "already running"; exit 0; fi
	cd "$REPO" || exit 1
	[ -x result-linux-builder/bin/create-builder ] || nix build .#packages.aarch64-darwin.linux-builder -o result-linux-builder || exit 1
	# from INSIDE the repo: the disk (nixos.qcow2, store-*.img, vzvm.json, keys/) is found relative to the working directory
	nohup ./result-linux-builder/bin/create-builder > "$REPO/builder.log" 2>&1 &
	echo "started (log: builder.log); waiting for the guest to accept logins..."
	n=0
	until $SSH true 2>/dev/null; do n=$((n + 1)); [ "$n" -ge 40 ] && { echo "not up after ~2 min: see builder.log"; exit 1; }; sleep 3; done
	echo "builder is up"
	;;
stop)
	pid=$(vzvm_pid)
	[ -n "$pid" ] || { echo "not running"; exit 0; }
	pgrep -f "nix build|nix-build|nix-store --realise" >/dev/null 2>&1 && { echo "a nix build seems to be running; stop refused (finish it first)"; exit 1; }
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
	;;
*)
	echo "usage: $0 status|start|stop" >&2
	exit 2
	;;
esac
