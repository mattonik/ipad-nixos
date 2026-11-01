# KUnit run of the J81 driver suites on QEMU arm64 (kernel/kunit/README.md).
#
# Takes the exact patched source tree of the Wi-Fi base kernel (so the driver code under test is the code that ships), adds the
# test hook and test files from kernel/kunit/, and runs tools/testing/kunit/kunit.py: a small separate kernel built from
# j81.kunitconfig, booted in qemu-system-aarch64 -machine virt. Never part of a payload. Built natively on aarch64-linux.
# The build fails when any test fails; SKIPs are listed in the log.
{ stdenv
, lib
, kernelSrc
, python3
, qemu_test
, bc
, bison
, flex
, perl
, gzip
, which
}:

stdenv.mkDerivation {
  name = "j81-kunit";
  src = kernelSrc;

  nativeBuildInputs = [ python3 qemu_test bc bison flex perl gzip which ];

  dontConfigure = true;
  dontFixup = true;

  postPatch = ''
    patch -p1 < ${./0001-bq27xxx-hdq-uart-kunit-hook.patch}
    cp ${./bq27xxx_battery_hdq_uart_kunit.c} drivers/power/supply/bq27xxx_battery_hdq_uart_kunit.c
    patchShebangs scripts tools/testing/kunit
  '';

  buildPhase = ''
    runHook preBuild
    export KBUILD_BUILD_HOST=nix KBUILD_BUILD_USER=nix KBUILD_BUILD_TIMESTAMP=@0
    mkdir -p "$out"
    status=0
    python3 tools/testing/kunit/kunit.py run \
      --arch=arm64 \
      --kunitconfig=${./j81.kunitconfig} \
      --build_dir="$TMPDIR/kunit-build" \
      --jobs="$NIX_BUILD_CORES" \
      --timeout=900 \
      --json="$out/results.json" \
      2>&1 | tee "$out/kunit.log" || status=$?  # stdenv runs with pipefail, so this is kunit.py's status
    cp "$TMPDIR/kunit-build/.config" "$out/kunit.config" || true
    if [ "$status" -ne 0 ]; then
      echo "kunit.py failed with status $status; see the log above" >&2
      exit "$status"
    fi
    runHook postBuild
  '';

  installPhase = "true";

  meta = {
    description = "KUnit tests of the J81 HDQ battery transport, run on QEMU arm64";
    platforms = [ "aarch64-linux" ];
  };
}
