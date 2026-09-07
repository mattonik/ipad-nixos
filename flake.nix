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
          nativeBuildInputs = [ pkgs.gzip pkgs.dtc ];
        } ''
          mkdir -p "$out"
          cp ${inputs.hoolockDocs}/binaries/Pongo.bin "$out/Pongo.bin"
          cp ${inputs.hoolockM1n1}/m1n1.bin "$out/m1n1.bin"
          gzip -n -c ${historicalKernel}/Image > "$out/Image.gz"
          # 2026-09-07: switched from the modern (mainline-sourced) DTB back
          # to the HISTORICAL kernel's own bundled one, now that the reason
          # for the earlier switch (a CPU reg-cell bug) is independently
          # patchable and the historical DTB has something mainline's
          # doesn't: a real T7001 USB-device-controller node
          # (usbdev@20c100000, compatible "apple,t7000-usb"), matched by a
          # real driver in this same historical kernel
          # (drivers/usb/dwc2/params.c). The modern DTB has no USB
          # controller node at all -- confirmed the first time Linux
          # reached a live shell here: g_ether logged "couldn't find an
          # available UDC", so its own telnet debug-shell had no network
          # link to be reached over. See docs/software-only-control.md.
          #
          # Same two structural defects the modern-DTB fix addressed are
          # patched here too, since they're properties of the *historical*
          # DTB, not specific to which DTB was in use:
          #
          # 1. /cpus declares #address-cells=1 (a single-cell "reg" per
          #    CPU), but m1n1's dt_set_cpus() (src/kboot.c) reads that
          #    property with fdt64_ld() -- an 8-byte load. Against a 4-byte
          #    property that over-reads into adjacent DTB data, producing a
          #    corrupted "expected MPIDR" and a hard-fail "DT CPU 1 MPIDR
          #    mismatch" on real hardware (confirmed running the modern DTB
          #    variant of this exact bug -- docs/software-only-control.md).
          #    Converted to the binding's correct #address-cells=2, two-cell
          #    reg format, matching mainline's current t7001.dtsi.
          # 2. The historical DTB has no /chosen/framebuffer node at all
          #    (unlike the modern one, which at least had a misnamed
          #    placeholder) -- m1n1's dt_set_fb() (src/kboot.c) looks it up
          #    by the exact path /chosen/framebuffer via fdt_path_offset()
          #    and silently skips console setup if it's missing (confirmed
          #    non-fatal on real hardware, see docs/software-only-control.md
          #    for the exact "FDT: No framebuffer found" case). Added a
          #    minimal placeholder node at that exact path; m1n1 renames it
          #    to framebuffer@<real base> and fills in
          #    reg/width/height/stride/format itself once found, so the
          #    placeholder's own field values don't matter. Unlike the
          #    modern DTB, this historical one has no PMGR power-domain
          #    nodes at all (predates that level of hardware description),
          #    so no power-domains reference is needed here -- the
          #    pd_ignore_unused/clk_ignore_unused bootargs fix below still
          #    applies globally as a safety net for whatever domains this
          #    DTB does describe.
          dtc -I dtb -O dts ${historicalKernel}/dtbs/apple/t7001-j81.dtb \
            | sed \
                -e '/^\tcpus {$/,/^\t};$/ s/#address-cells = <0x01>;/#address-cells = <0x02>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x00>;/reg = <0x00 0x00>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x01>;/reg = <0x00 0x01>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x02>;/reg = <0x00 0x02>;/' \
                -e '/^\tchosen {$/,/^\t};$/ s/ranges;/ranges;\n\t\tframebuffer {\n\t\t\tcompatible = "apple,simple-framebuffer", "simple-framebuffer";\n\t\t\treg = <0x00 0x00 0x00 0x00>;\n\t\t\tstatus = "disabled";\n\t\t};/' \
            | dtc -I dts -O dtb -o "$out/t7001-j81.dtb"
          cp ${inputs.linuxAppleResources}/debug_initrd.img "$out/initramfs.gz"
          # m1n1's payload parser (src/payload.c check_var()) requires a
          # trailing newline to find the end of a "chosen.X=value" line --
          # without it, it can't terminate the value and falls through to
          # "Unknown payload", exactly what a real hardware run hit here.
          #
          # PMOS_NO_OUTPUT_REDIRECT: the bundled debug_initrd.img is a 2020
          # postmarketOS image for a Sony Xperia Z5. Its /init calls
          # setup_log() (init_functions.sh), which execs PID 1's own stdout
          # and stderr into /pmOS_init.log -- a RAM-only file this project
          # has no way to read -- unless this exact token appears in
          # /proc/cmdline. Confirmed by inspecting the actual bundled
          # init_functions.sh; see docs/software-only-control.md's
          # "Software follow-up" section for the full byte-level evidence
          # (including why the subsequent black screen is a >99%-black
          # 1080x1920 Xperia splash image, not a crash).
          #
          # 2026-09-07, second round: with PMOS_NO_OUTPUT_REDIRECT applied
          # and the attempt re-run at 120fps, the "### postmarketOS
          # initramfs ###" line that setup_log() prints unconditionally --
          # before it even checks the redirect flag -- has never appeared
          # in any captured frame, across either attempt. That means PID 1
          # likely never starts at all; the black screen is upstream of
          # userspace, inside the kernel itself. A concrete, well-targeted
          # candidate: Apple's PMGR power-domain driver
          # (drivers/soc/apple/apple-pmgr-pwrstate.c) uses the generic
          # power-domain (genpd) framework, whose genpd_power_off_unused()
          # runs as a late_initcall() -- right after the device-driver
          # probing this project has now watched complete on video every
          # time -- and powers off any domain with no active consumer.
          # There is no real Linux display driver holding the inherited
          # framebuffer's power domain open, so it's a plausible candidate
          # for being powered off right when the screen goes black.
          # pd_ignore_unused/clk_ignore_unused (drivers/base/power/domain.c,
          # drivers/clk/clk.c) are the real, standard kernel parameters that
          # disable this specific behavior -- added to test it directly.
          printf '%s\n' 'chosen.bootargs=console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused' \
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
