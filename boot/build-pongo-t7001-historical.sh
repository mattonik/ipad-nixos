#!/usr/bin/env bash
# Build the unmodified June 2022 T7001 PongoOS control from a clean checkout.
set -euo pipefail

project_dir=$(cd "$(dirname "$0")/.." && pwd)
source_dir=${1:?"usage: $0 /path/to/clean/konradybcio-pongoOS-checkout"}
revision=a3b1f652f691ff35ad1cd7840f3dfe11afdd82c9
output="$project_dir/boot/Pongo-t7001-historical.bin"
pongo_cc=${PONGO_CC:?Set PONGO_CC to Apple Clang 14.0.0 (clang-1400.0.29.202)}
pongo_ld=${PONGO_LD:?Set PONGO_LD to the Xcode 14.2 ld64-820.1 linker}

case "$("$pongo_cc" --version)" in
    *'Apple clang version 14.0.0 (clang-1400.0.29.202)'*) ;;
    *) echo "Historical PongoOS must be built with Apple Clang 14.0.0 (clang-1400.0.29.202)" >&2; exit 1 ;;
esac
case "$("$pongo_ld" -v 2>&1)" in
    *'PROJECT:ld64-820.1'*) ;;
    *) echo "PONGO_LD must be Xcode 14.2 ld64-820.1" >&2; exit 1 ;;
esac
test "$(git -C "$source_dir" rev-parse HEAD)" = "$revision" || {
    echo "PongoOS checkout must be exactly $revision" >&2
    exit 1
}
git -C "$source_dir" submodule update --init --recursive
test -z "$(git -C "$source_dir" status --porcelain --untracked-files=normal)" || {
    echo "PongoOS checkout must be clean" >&2
    exit 1
}

# Clang 14 diagnoses two variables that the 2022 compiler did not; suppressing
# that diagnostic preserves the historical source and generated code.
make -C "$source_dir" -j"${JOBS:-4}" \
    EMBEDDED_CC="$pongo_cc" \
    EMBEDDED_LDFLAGS="-fuse-ld=$pongo_ld" \
    EMBEDDED_CFLAGS=-Wno-unused-but-set-variable \
    build/Pongo.bin
install -m 0644 "$source_dir/build/Pongo.bin" "$output"
shasum -a 256 "$output"
