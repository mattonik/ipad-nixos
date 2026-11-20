#!/bin/sh
# Build and verify on an Apple Silicon Mac with Xcode and the iPhoneOS SDK.
set -eu
cd "$(dirname "$0")"
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
for sdk in macosx iphoneos; do
    case "$sdk" in
        macosx) target=arm64-apple-macos11 ;;
        iphoneos) target=arm64-apple-ios15.0 ;;
    esac
    xcrun --sdk "$sdk" clang -target "$target" -std=c11 -O2 -ffreestanding \
        -fno-stack-protector -Wall -Wextra -Werror -c probe.c -o "$out/$sdk.o"
    xcrun llvm-objdump -s --section=__text "$out/$sdk.o" > "$out/$sdk.dump"
    sed -n '/^ [[:xdigit:]][[:xdigit:]]*[[:space:]]/p' "$out/$sdk.dump" > "$out/$sdk.text"
    test -s "$out/$sdk.text"
done
cmp "$out/macosx.text" "$out/iphoneos.text"
xcrun --sdk macosx clang -arch arm64 -O2 -Wall -Wextra -Werror \
    "$out/macosx.o" test_probe.c -o "$out/test"
"$out/test"
echo 'PASS: host-tested and iPadOS __text bytes match'
