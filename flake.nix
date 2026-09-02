{
  description = "iPad NixOS - Linux on iPad via checkm8/pongoOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv = {
      url = "github:cachix/devenv";
      inputs.nixpkgs.follows = "nixpkgs";
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
          # 16KB page size is a kernel concern, not a userspace concern.
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

      # Cross-compiled packages for iPad (aarch64, 16KB pages)
      packages.${linuxBuildSystem} = {
        # Linux kernel for iPad Air 2 (A8X)
        kernel = pkgsCross.callPackage ./kernel {};

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
