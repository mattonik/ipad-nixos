#!/bin/sh
# Rebuild one kernel driver and swap it on the booted iPad, without a kernel build or a DFU cycle. Guide: docs/kmod-reload.md.
#
#   tools/kmod.sh extract NAME        copy the kernel's own source of NAME into artifacts/kmod/NAME/ (writable work copy; refuses to overwrite)
#   tools/kmod.sh build NAME          build artifacts/kmod/NAME/ out of tree against the modular kernel -> artifacts/kmod/NAME.ko
#   tools/kmod.sh load NAME           copy artifacts/kmod/NAME.ko to the iPad (SHA-256 checked), rmmod the running copy, insmod, show dmesg
#   tools/kmod.sh stock NAME          build and load the unmodified module (first load after boot, or to undo an experiment)
#   tools/kmod.sh diff NAME           diff the work copy against the kernel's source (the start of a kernel/patches/ patch)
#
# NAME is one of the modules the modular kernel builds as =m: spi-apple, apple_z2. The payload must be m1n1-hoolock-wifi-touch-kmod
# (or another payload built on hoolockWifiKmodKernel): a module only loads into the exact kernel it was built against.
# Results are incremental and labelled as such: when an experiment works, turn `diff` into a patch and do the reproducible Nix build.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK="$REPO/artifacts/kmod"
SYSTEM=x86_64-linux
NIX="nix --extra-experimental-features nix-command --extra-experimental-features flakes"
IPAD=${IPAD:-root@172.16.42.1}
KEY=${IPAD_KEY:-$REPO/artifacts/live/ssh/ipad_ed25519}
# The RAM root regenerates its host key every boot; skip host-key checks for this USB link only.
SSH="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR $IPAD"

say() { echo "kmod: $*"; }
die() { echo "kmod: $*" >&2; exit 1; }

[ $# -eq 2 ] || { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
action=$1
name=$2
case "$name" in
  spi-apple|apple_z2) ;;
  brcmfmac*) die "brcmfmac stays built in: reloading it reset an iPad 6 once (Orchard docs/integration/j71t.md)";;
  *) die "unknown module '$name' (reloadable: spi-apple, apple_z2)";;
esac
module=$(echo "$name" | tr - _)   # the name the running kernel uses (rmmod, /sys/module)

flake_expr() { # $1: an attribute path below packages.$SYSTEM
  echo "(builtins.getFlake \"git+file://$REPO\").packages.$SYSTEM.$1"
}

stock_src() {
  $NIX build --no-link --print-out-paths "$REPO#packages.$SYSTEM.j81-kmod-src-$name"
}

build_from() { # $1: source directory; prints the output store path
  src=$1
  $NIX build --impure --no-link --print-out-paths --expr \
    "($(flake_expr "j81-kmod-$name")).overrideAttrs (_: { src = builtins.path { path = \"$src\"; name = \"j81-kmod-src-$name\"; }; })"
}

load_ko() { # $1: the .ko file on the Mac
  ko=$1
  sum=$(shasum -a 256 "$ko" | cut -d' ' -f1)
  say "copying $(basename "$ko") ($sum) to $IPAD"
  $SSH "cat > /tmp/$name.ko" < "$ko"
  remote=$($SSH "sha256sum /tmp/$name.ko" | cut -d' ' -f1)
  [ "$remote" = "$sum" ] || die "SHA-256 mismatch after copy (iPad has $remote); nothing loaded"
  # rmmod fails harmlessly when the module is not loaded yet (first load after boot).
  $SSH "if [ -d /sys/module/$module ]; then rmmod $module || exit 1; fi; dmesg -c >/dev/null; insmod /tmp/$name.ko; rc=\$?; dmesg; exit \$rc" \
    || die "insmod failed (see dmesg above)"
  say "$name loaded"
}

case "$action" in
  extract)
    [ ! -e "$WORK/$name" ] || die "$WORK/$name exists; remove it first to start over"
    mkdir -p "$WORK"
    cp -R "$(stock_src)/." "$WORK/$name/"
    chmod -R u+w "$WORK/$name"
    say "work copy in $WORK/$name"
    ;;
  build)
    [ -d "$WORK/$name" ] || die "no work copy; run: tools/kmod.sh extract $name"
    out=$(build_from "$WORK/$name")
    cp -f "$out/$name.ko" "$WORK/$name.ko"
    chmod u+w "$WORK/$name.ko"
    say "built $WORK/$name.ko (incremental, from the work copy; store path $out)"
    ;;
  load)
    [ -f "$WORK/$name.ko" ] || die "nothing built; run: tools/kmod.sh build $name"
    load_ko "$WORK/$name.ko"
    ;;
  stock)
    out=$($NIX build --no-link --print-out-paths "$REPO#packages.$SYSTEM.j81-kmod-$name")
    load_ko "$out/$name.ko"
    ;;
  diff)
    [ -d "$WORK/$name" ] || die "no work copy; run: tools/kmod.sh extract $name"
    diff -ru --exclude=Kbuild "$(stock_src)" "$WORK/$name" || true
    ;;
  *) die "unknown action '$action' (extract, build, load, stock, diff)";;
esac
