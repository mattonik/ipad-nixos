#!/bin/sh
# Build the two guarded PLL-word writers (freestanding AArch64, plain clang + lld, no libc).
# usage: boot/build_pmgr_pll_set.sh <out dir>   (needs llvm@14 clang/lld; adds a temporary ld.lld shim dir to PATH)
set -eu
here=$(cd "$(dirname "$0")" && pwd); out=${1:?out dir}; mkdir -p "$out"
LLVM=${LLVM:-/opt/homebrew/opt/llvm@14/bin}; shim=$(mktemp -d); ln -s "$LLVM/lld" "$shim/ld.lld"; PATH="$shim:$LLVM:$PATH"
for spec in "pll1 0x20e001008UL 0x80480348U 0x40480348U" "pll4 0x20e004008UL 0x88480348U 0x48480348U"; do
	set -- $spec
	clang --target=aarch64-linux-gnu -O2 -ffreestanding -fno-stack-protector -fno-builtin -nostdlib -static -fuse-ld=lld \
		-Wl,-e,_start -DTAG="\"$1\"" -DADDR="$2" -DADDR_STR="\"${2%UL}\"" -DOLD="$3" -DNEW="$4" "$here/pmgr-pll-set.c" -o "$out/pmgr-$1-set"
done
rm -rf "$shim"; ( cd "$out" && shasum -a 256 pmgr-pll1-set pmgr-pll4-set )
