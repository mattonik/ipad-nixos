# m1n1 built from source: HoolockLinux m1n1 `idevice` at the same commit as the
# nightly zip the payloads used before (d5a10ac), plus two OrchardLinux loader
# patches that forward the touchscreen calibration from the ADT to the FDT
# (docs/m1n1-from-source.md). With a `touchscreen0` alias in the DTB, m1n1 copies
# the ADT `multi-touch` calibration properties into that node as
# `apple,z2-*-cal-blob`, so no calibration bytes ever live in this repository.
#
# Built on the Mac (aarch64-darwin) rather than on the Linux builder VM: m1n1 is
# a freestanding aarch64 image, the Mac has the network access the cargo crates
# need, and m1n1.bin is the same bytes whichever host built it. Toolchain as in
# Orchard's boot/m1n1/build: clang/lld with USE_CLANG=1, CHAINLOADING=1, Rust 1.90.0
# with the aarch64-unknown-none-softfloat target.

{ lib
, stdenv
, src
, rev
, llvmPackages
, rust-bin
, rustPlatform
}:

let
  rust = rust-bin.stable."1.90.0".minimal.override {
    targets = [ "aarch64-unknown-none-softfloat" ];
  };
in
stdenv.mkDerivation {
  pname = "m1n1-hoolock";
  version = "unstable-${builtins.substring 0 7 rev}";
  inherit src;

  patches = [
    ./patches/0001-orchard-fill-in-a9-a11-device-data-generically.patch
    ./patches/0002-orchard-forward-touchscreen-proximity-calibration.patch
  ];

  cargoRoot = "rust";
  cargoDeps = rustPlatform.importCargoLock {
    lockFile = "${src}/rust/Cargo.lock";
    outputHashes = {
      "fatfs-0.4.0" = "sha256-tcchdtuIIN8fkLy/qf9hazkPGT2kdYuPUtC/C1bRfIQ=";
    };
  };

  nativeBuildInputs = [ rust rustPlatform.cargoSetupHook ];

  # The source has no .git, so version.sh would print "unknown".
  M1N1_VERSION_TAG = "hoolock-${builtins.substring 0 7 rev}-ipad-nixos";

  makeFlags = [
    "USE_CLANG=1"
    "ARCH=aarch64-linux-gnu"
    "TOOLCHAIN=${llvmPackages.clang-unwrapped}/bin/"
    "LLDDIR=${llvmPackages.lld}/bin/"
    "OBJCOPY=${llvmPackages.llvm}/bin/llvm-objcopy"
    "CHAINLOADING=1"
  ];

  enableParallelBuilding = true;

  installPhase = ''
    runHook preInstall
    install -Dm644 build/m1n1.bin "$out/m1n1.bin"
    install -Dm644 build/m1n1-idevice.macho "$out/m1n1-idevice.macho"
    install -Dm644 build/monitor-stub.macho "$out/monitor-stub.macho"
    runHook postInstall
  '';

  meta = {
    description = "HoolockLinux m1n1 (A7-A11) with OrchardLinux ADT calibration forwarding";
    homepage = "https://github.com/HoolockLinux/m1n1";
    license = lib.licenses.mit;
  };
}
