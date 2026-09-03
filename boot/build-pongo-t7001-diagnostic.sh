#!/usr/bin/env bash
# Build the guarded T7001 diagnostic PongoOS from a clean pinned checkout.
set -euo pipefail

project_dir=$(cd "$(dirname "$0")/.." && pwd)
source_dir=${1:?"usage: $0 /path/to/clean/PongoOS-checkout"}
revision=742d92a023d16c4cc9ebf9cb73b708bf92c52808
output="$project_dir/boot/Pongo-t7001-diagnostic.bin"
pongo_cc=${PONGO_CC:-clang}
pongo_ld=${PONGO_LD:-/usr/bin/ld}

"$pongo_cc" --version | grep -q '^clang version 11\.' || {
    echo "PongoOS must be built with Nix Clang 11; see docs/project-status.md" >&2
    exit 1
}
test -x "$pongo_ld" || {
    echo "PONGO_LD must name an executable Mach-O linker" >&2
    exit 1
}

test "$(git -C "$source_dir" rev-parse HEAD)" = "$revision" || {
    echo "PongoOS checkout must be exactly $revision" >&2
    exit 1
}
git -C "$source_dir" submodule update --init --recursive
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
