#!/usr/bin/env bash
# Build the guarded T7001 diagnostic PongoOS from a clean pinned checkout.
set -euo pipefail

project_dir=$(cd "$(dirname "$0")/.." && pwd)
source_dir=${1:?"usage: $0 /path/to/clean/PongoOS-checkout"}
revision=742d92a023d16c4cc9ebf9cb73b708bf92c52808
output="$project_dir/boot/Pongo-t7001-diagnostic.bin"
pongo_cc=${PONGO_CC:?Set PONGO_CC to Apple Clang 14.0.0 (clang-1400.0.29.202); see docs/project-status.md}
pongo_ld=${PONGO_LD:?Set PONGO_LD to the Xcode 14.2 ld; see docs/project-status.md}

case "$("$pongo_cc" --version)" in
    *'Apple clang version 14.0.0 (clang-1400.0.29.202)'*) ;;
    *) echo "PongoOS must be built with Apple Clang 14.0.0 (clang-1400.0.29.202); see docs/project-status.md" >&2; exit 1 ;;
esac
test -x "$pongo_ld" || {
    echo "PONGO_LD must name an executable Mach-O linker" >&2
    exit 1
}
case "$("$pongo_ld" -v 2>&1)" in
    *'PROJECT:ld64-820.1'*) ;;
    *) echo "PONGO_LD must be Xcode 14.2 ld64-820.1; see docs/project-status.md" >&2; exit 1 ;;
esac

test "$(git -C "$source_dir" rev-parse HEAD)" = "$revision" || {
    echo "PongoOS checkout must be exactly $revision" >&2
    exit 1
}
git -C "$source_dir" submodule update --init --recursive
test ! -e "$source_dir/build/Pongo.bin" &&
    test ! -e "$source_dir/newlib/build/Makefile" &&
    test ! -e "$source_dir/newlib/aarch64-none-darwin/fixup/libc.a" || {
    echo "PongoOS checkout contains generated build output; use a fresh checkout." >&2
    exit 1
}
git -C "$source_dir" diff --quiet || {
    echo "PongoOS checkout must be clean; use a fresh checkout." >&2
    exit 1
}
git -C "$source_dir" diff --cached --quiet || {
    echo "PongoOS checkout must be clean; use a fresh checkout." >&2
    exit 1
}
git -C "$source_dir" apply --check "$project_dir/boot/pongo-t7001.patch"
git -C "$source_dir" apply "$project_dir/boot/pongo-t7001.patch"
make -C "$source_dir" -j"${JOBS:-4}" EMBEDDED_CC="$pongo_cc" EMBEDDED_LD="$pongo_ld"
install -m 0644 "$source_dir/build/Pongo.bin" "$output"
shasum -a 256 "$output"
