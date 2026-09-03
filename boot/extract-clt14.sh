#!/usr/bin/env bash
# Extract the verified Xcode 14.2 Command Line Tools without installing it.
set -euo pipefail

image=${1:?"usage: $0 Command_Line_Tools_for_Xcode_14.2.dmg output-directory"}
output=${2:?"usage: $0 Command_Line_Tools_for_Xcode_14.2.dmg output-directory"}
expected='Apple clang version 14.0.0 (clang-1400.0.29.202)'

test -f "$image" || { echo "CLT image not found: $image" >&2; exit 1; }
test ! -e "$output" || { echo "output already exists: $output" >&2; exit 1; }

mount=$(mktemp -d /tmp/clt14-mount.XXXXXX)
package=$(mktemp -d /tmp/clt14-package.XXXXXX)
attached=false

cleanup() {
    if [ "$attached" = true ]; then
        hdiutil detach "$mount" >/dev/null || true
    fi
    rm -rf "$mount" "$package"
}
trap cleanup EXIT

hdiutil verify "$image"
hdiutil attach "$image" -readonly -nobrowse -mountpoint "$mount" >/dev/null
attached=true
pkg="$mount/Command Line Tools.pkg"
pkgutil --check-signature "$pkg" | grep -Fq 'Status: signed Apple Software'
xar -xf "$pkg" -C "$package"
hdiutil detach "$mount" >/dev/null
attached=false

mkdir "$output"
python3 - "$package/CLTools_Executables.pkg/Payload" <<'PY' | (cd "$output" && cpio -idm --quiet)
import lzma
import struct
import sys


def read_exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise RuntimeError(f"truncated payload: wanted {size}, got {len(data)}")
    return data


with open(sys.argv[1], "rb") as stream:
    if read_exact(stream, 4) != b"pbzx":
        raise RuntimeError("not an Apple pbzx payload")
    flags = struct.unpack(">Q", read_exact(stream, 8))[0]
    while flags & (1 << 24):
        flags = struct.unpack(">Q", read_exact(stream, 8))[0]
        size = struct.unpack(">Q", read_exact(stream, 8))[0]
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        while size:
            chunk = read_exact(stream, min(size, 1024 * 1024))
            size -= len(chunk)
            sys.stdout.buffer.write(decoder.decompress(chunk))
        if not decoder.eof:
            raise RuntimeError("truncated XZ stream")
PY

compiler="$output/Library/Developer/CommandLineTools/usr/bin/clang"
case "$("$compiler" --version)" in
    *"$expected"*) ;;
    *) echo "extracted compiler is not $expected" >&2; exit 1 ;;
esac
linker="$output/Library/Developer/CommandLineTools/usr/bin/ld"
case "$("$linker" -v 2>&1)" in
    *'PROJECT:ld64-820.1'*) ;;
    *) echo "extracted linker is not Xcode 14.2 ld64-820.1" >&2; exit 1 ;;
esac
printf 'PONGO_CC=%q\n' "$compiler"
printf 'PONGO_LD=%q\n' "$linker"
