{
  description = "iPad NixOS - Linux on iPad via checkm8/pongoOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv = {
      url = "github:cachix/devenv";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    linuxApple519 = {
      url = "github:konradybcio/linux-apple/a907b05f09bfea50511ea0e82dc14f70d999ba37";
      flake = false;
    };
    linuxAppleResources = {
      url = "github:SoMainline/linux-apple-resources/30780ec0fecdab849bb812e1dde52b87e614f45b";
      flake = false;
    };
    hoolockDocs = {
      url = "github:HoolockLinux/docs/23ebe1fbc375599221553a7e1815e5de182a6b42";
      flake = false;
    };
    # Fetched as a proper flake input (resolved on the Mac, which has real
    # internet access) rather than via pkgs.fetchzip inside the package body
    # -- that fetch used to run on the offline cross-compilation builder,
    # which cannot resolve nightly.link/tarballs.nixos.org. Same class of fix
    # already applied to linuxApple519/linuxAppleResources above.
    hoolockM1n1 = {
      url = "https://nightly.link/hoolocklinux/m1n1/actions/runs/33380676898/m1n1.zip";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, devenv, ... }@inputs:
    let
      linuxBuildSystem = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${linuxBuildSystem};
      darwinPkgs = import nixpkgs {
        system = "aarch64-darwin";
        overlays = [
          # libplist's ostep2 test currently crashes on this Darwin host;
          # it is only a build-time check for the irecovery dependency.
          (_final: prev: {
            libplist = prev.libplist.overrideAttrs (_: { doCheck = false; });
          })
        ];
      };
      darwinGaster = darwinPkgs.callPackage ./boot/gaster.nix {};

      # Cross-compilation: build on x86_64, target aarch64 (iPad ARM64)
      # glibc variant — used for the kernel build (buildLinux handles cross internally)
      pkgsCross = import nixpkgs {
        localSystem.system = linuxBuildSystem;
        crossSystem.system = "aarch64-linux";
      };

      # musl variant — for the initramfs.
      # musl gives fully self-contained binaries: no glibc version skew,
      # simpler static linking.  aarch64-unknown-linux-musl is the triple.
      pkgsCrossMusl = import nixpkgs {
        localSystem.system = linuxBuildSystem;
        crossSystem = {
          config = "aarch64-unknown-linux-musl";
          # The 4 KiB page size is a kernel concern, not a userspace concern.
          # musl and busybox do not need a special page-size override here.
        };
      };

      # Explicitly opt in to including a local *public* SSH key.  Keeping this
      # environment-derived makes ordinary builds key-free and reproducible.
      authorizedKeysFile =
        let keyPath = builtins.getEnv "IPAD_AUTHORIZED_KEYS";
        in if keyPath == "" then null else builtins.path {
          path = builtins.toPath keyPath;
          name = "ipad-authorized-keys";
        };
    in
    {
      # Dev shell (x86_64 tools for RE, flashing, serial, etc.)
      devShells.${linuxBuildSystem}.default = devenv.lib.mkShell {
        inherit inputs pkgs;
        modules = [ ./devenv.nix ];
      };

      devShells.aarch64-darwin.default = darwinPkgs.mkShell {
        packages = [
          darwinGaster
          darwinPkgs.libirecovery
          darwinPkgs.python3
          darwinPkgs.python3Packages.pyusb
          darwinPkgs.xz
        ];
      };

      # Cross-compiled packages for iPad (aarch64, 4 KiB pages on A7-A8X)
      packages.${linuxBuildSystem} =
        let
          historicalKernel = pkgsCross.callPackage ./kernel/historical.nix {
            source = inputs.linuxApple519;
            historicalConfig = "${inputs.linuxAppleResources}/example.config";
          };
          modernKernel = pkgsCross.callPackage ./kernel {};
        in {
        # Linux kernel for iPad Air 2 (A8X)
        kernel = modernKernel;

        # Exact kernel branch used by the June 2022 T7001 proof. Keep this as
        # a control; do not add current-tree fixes until it has booted as-is.
        historical-kernel = historicalKernel;

        # Kernel, the published multi-device DTB pack, and debug initramfs in
        # the exact file layout consumed by the historical PongoOS loader.
        historical-payload = pkgs.runCommand "ipad-air2-linux-2022-control" {
          nativeBuildInputs = [ pkgs.xz pkgs.xxd ];
        } ''
          mkdir -p "$out"
          xz --format=lzma -c ${historicalKernel}/Image > "$out/Image.lzma"
          mkdir -p work/arch/arm64/boot/dts
          ln -s ${historicalKernel}/dtbs/apple work/arch/arm64/boot/dts/apple
          (cd work && bash ${inputs.linuxAppleResources}/dtbpack.sh)
          mv work/dtbpack "$out/dtbpack"
          cp ${inputs.linuxAppleResources}/debug_initrd.img "$out/initrd"
        '';

        # Current software-only route: PongoOS bootm -> iDevice m1n1 -> the
        # pinned historical kernel. m1n1 itself can be sent first as a visible
        # handoff diagnostic without involving Linux.
        m1n1-control = pkgs.runCommand "ipad-air2-m1n1-control" {
          nativeBuildInputs = [ pkgs.gzip ];
        } ''
          mkdir -p "$out"
          cp ${inputs.hoolockDocs}/binaries/Pongo.bin "$out/Pongo.bin"
          cp ${inputs.hoolockM1n1}/m1n1.bin "$out/m1n1.bin"
          gzip -n -c ${historicalKernel}/Image > "$out/Image.gz"
          # Deliberately the MODERN (mainline-sourced) DTB, not the
          # historical kernel's own bundled one: the 2022 DT declares CPU
          # nodes with #address-cells=1 (a single-cell "reg"), but m1n1's
          # dt_set_cpus() (src/kboot.c) reads that property with fdt64_ld()
          # -- an 8-byte load. Against a 4-byte property that over-reads
          # into adjacent DTB data, producing a corrupted "expected MPIDR"
          # and a hard-fail "DT CPU 1 MPIDR mismatch" on real hardware
          # (confirmed on this exact device -- see docs/software-only-control.md).
          # Mainline's current t7001.dtsi already uses the correct
          # #address-cells=2 two-cell reg format m1n1 expects; the kernel
          # Image itself is still the historical, pinned one.
          cp ${modernKernel}/dtbs/apple/t7001-j81.dtb "$out/t7001-j81.dtb"
          cp ${inputs.linuxAppleResources}/debug_initrd.img "$out/initramfs.gz"
          # m1n1's payload parser (src/payload.c check_var()) requires a
          # trailing newline to find the end of a "chosen.X=value" line --
          # without it, it can't terminate the value and falls through to
          # "Unknown payload", exactly what a real hardware run hit here.
          printf '%s\n' 'chosen.bootargs=console=tty0 loglevel=8 ignore_loglevel rdinit=/init' \
            > "$out/bootargs"
          cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" \
            "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
          sha256sum "$out/Pongo.bin" "$out/m1n1.bin" "$out/m1n1-linux.bin" \
            > "$out/SHA256SUMS"
        '';

        # Minimal initramfs — entire root filesystem in RAM
        # Build with SSH access:
        # IPAD_AUTHORIZED_KEYS=/absolute/path/key.pub nix build --impure \
        #   .#packages.x86_64-linux.initramfs
        # Output: result/initrd  (symlink to result/initrd.zst)
        initramfs = pkgsCrossMusl.callPackage ./nixos/initramfs.nix {
          inherit authorizedKeysFile;
        };

        gaster = pkgs.callPackage ./boot/gaster.nix {};
      };

      packages.aarch64-darwin.gaster = darwinGaster;
    };
}
