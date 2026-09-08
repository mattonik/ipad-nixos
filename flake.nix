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
    # Newer-kernel candidate researched after Round 8 (see
    # research/t7001-usb-next.md's "Decision, 2026-09-07"): tracks mainline
    # Linux 7.3-rc1, restores real dwc2 DMA hardware-capability detection
    # instead of the historical fork's hardcoded PIO fallback, and already
    # has a t7001-j81.dts for this exact board. Pinned to the same commit
    # verified against the live repository during that research.
    hoolockLinux = {
      url = "github:HoolockLinux/linux/6831bc701a6ce059e71e5aaa9488c9195bea6927";
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
          # example.config sets CONFIG_USB_ETH_EEM=y, which makes the g_ether
          # gadget present CDC-EEM instead of CDC-ECM as its non-Windows USB
          # configuration (drivers/usb/gadget/legacy/Kconfig: "If you say y
          # here, the Ethernet gadget driver will use the EEM protocol
          # rather than ECM"). Confirmed on real hardware, 2026-09-07: once
          # Linux boots and g_ether binds, the Mac's ioreg shows the device
          # matched+active but stuck on configuration 1 (class 0x02/subclass
          # 0x0c/proto 0x07 -- CDC-EEM) with configuration 2 being RNDIS
          # (class 0x02/subclass 0x02/proto 0xff, Microsoft's ACM+vendor
          # encoding) -- no CDC-ECM (subclass 0x06) offered at all, and
          # macOS has no in-box driver for either EEM or RNDIS, only ECM.
          # USB_ETH always `select`s USB_F_ECM regardless of this flag, so
          # disabling USB_ETH_EEM is enough to make g_ether fall back to
          # ECM without touching anything else.
          patchedHistoricalConfig = pkgs.runCommand "ipad-t7001-defconfig-usb-ecm" {} ''
            sed 's/^CONFIG_USB_ETH_EEM=y$/# CONFIG_USB_ETH_EEM is not set/' \
              ${inputs.linuxAppleResources}/example.config > "$out"
          '';
          historicalKernel = pkgsCross.callPackage ./kernel/historical.nix {
            source = inputs.linuxApple519;
            historicalConfig = patchedHistoricalConfig;
          };
          modernKernel = pkgsCross.callPackage ./kernel {};

          # config_16k defaults to 16K pages (A9-A11/T2); Hoolock's own setup
          # guide says to swap in CONFIG_ARM64_4K_PAGES for A7-A8X instead --
          # confirmed directly from that guide's text during the Round 8
          # follow-up research, not inferred from the filename. Same
          # sed-on-a-derivation technique as patchedHistoricalConfig above.
          #
          # CONFIG_BACKLIGHT_APPLE_PMIC stays enabled (config_16k's default):
          # its build failure under this project's GCC cross-toolchain
          # (drivers/video/backlight/apple_pmic_bl.c, missing default case
          # in a switch, -Werror=return-type) is now fixed properly at the
          # source in kernel/hoolock.nix's configuredSource, rather than
          # worked around by disabling the driver -- see that file's
          # comment. This DTB already has a matching, enabled DT node for
          # it (i2c@20a110000/pmic@3c/backlight@600), same as the RTC
          # (CONFIG_RTC_DRV_APPLE_PMIC, already =y here, untouched).
          patchedHoolockConfig = pkgs.runCommand "ipad-t7001-hoolock-defconfig-4k" {} ''
            sed \
              -e 's/^# CONFIG_ARM64_4K_PAGES is not set$/CONFIG_ARM64_4K_PAGES=y/' \
              -e 's/^CONFIG_ARM64_16K_PAGES=y$/# CONFIG_ARM64_16K_PAGES is not set/' \
              -e 's/^# CONFIG_I2C_CHARDEV is not set$/CONFIG_I2C_CHARDEV=y/' \
              ${inputs.hoolockDocs}/config_16k > "$out"
          '';
          hoolockKernel = pkgsCross.callPackage ./kernel/hoolock.nix {
            source = inputs.hoolockLinux;
            hoolockConfig = patchedHoolockConfig;
          };

          # BT-1 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md):
          # The transport-only UART3 DT patch deliberately has no Bluetooth
          # child. This userspace tool attaches the raw HCI UART independently;
          # see boot/btattach.nix for why it is a minimal source build rather
          # than the full BlueZ package.
          btattachPkg = pkgsCrossMusl.callPackage ./boot/btattach.nix {
            stdenvCross = pkgsCrossMusl.stdenv;
            bluezSrc = pkgsCrossMusl.bluez.src;
            bluezVersion = pkgsCrossMusl.bluez.version;
          };

          # BT-3 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md): m1n1's
          # own USB proxy mode doesn't enumerate on this hardware (tried
          # repeatedly, 2026-09-08), so the PMU GPIO2 register scan runs
          # from Linux instead, over the same pmic@3c I2C chip RTC/backlight
          # already prove works. i2c-tools is small and dependency-free
          # (unlike bluez, no glib/dbus-style chain to route around), so the
          # real package cross-compiles directly -- no from-scratch minimal
          # build needed here. Static for the same reason as btattach: the
          # debug initramfs's musl is a separate build from Nix's own, and
          # the stock package's dynamic linking against Nix's musl produced
          # a real "not found" failure on hardware (the ELF interpreter
          # path doesn't exist there) before this override was added.
          # lib/Module.mk documents its own static-build variables
          # (BUILD_DYNAMIC_LIB/BUILD_STATIC_LIB/USE_STATIC_LIB) -- disabling
          # the shared libi2c.so build entirely avoids it fighting a global
          # -static (which broke with "cannot find -lgcc_s" when the
          # Makefile's own `-shared` link line picked it up too).
          i2cToolsPkg = pkgsCrossMusl.i2c-tools.overrideAttrs (old: {
            # LDFLAGS=-static (a plain make variable the Makefile's own
            # $(CC) $(LDFLAGS) link line picks up directly), not
            # NIX_LDFLAGS -- that route left the tools/Module.mk link step
            # still pulling in shared libgcc_s ("cannot find -lgcc_s", no
            # static libgcc_s.a exists in this musl cross toolchain),
            # because it doesn't reach gcc's own driver-level "this is a
            # static link, use libgcc.a" detection the same way.
            makeFlags = old.makeFlags ++ [
              "BUILD_DYNAMIC_LIB=0"
              "BUILD_STATIC_LIB=1"
              "USE_STATIC_LIB=1"
              "LDFLAGS=-static"
            ];
          });
        in {
        # Linux kernel for iPad Air 2 (A8X)
        kernel = modernKernel;

        # Exact kernel branch used by the June 2022 T7001 proof. Keep this as
        # a control; do not add current-tree fixes until it has booted as-is.
        historical-kernel = historicalKernel;

        # Newer-kernel candidate researched after Round 8 (see
        # research/t7001-usb-next.md). Kept as its own independent output --
        # not yet wired into m1n1-control -- so the working historical
        # control stays the rollback path while this is evaluated.
        hoolock-kernel = hoolockKernel;

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
          # 3. Hardware-tested 2026-09-07 and hit "FDT: couldn't set
          #    cpu-release-addr property" / "Failed to prepare FDT!" / "No
          #    valid payload found" -- m1n1 fell back to its USB proxy
          #    instead of booting. First guess was a blob-space problem
          #    (fixed below with `-p 0x10000`) but a second hardware run
          #    with that padding hit the exact same failure -- reading
          #    m1n1's actual source (src/kboot.c dt_set_cpus()) showed why:
          #    it writes this property with fdt_setprop_inplace_u64(), and
          #    m1n1 *always* reopens the incoming DTB into its own
          #    generously-padded buffer first (fdt_open_into() with +96 KiB,
          #    src/kboot.c ~line 2925) regardless of how the blob we hand it
          #    was compiled -- so blob padding was never the issue.
          #    "Inplace" libfdt calls never grow the tree; they only
          #    overwrite an *existing* same-sized property's value, and
          #    fail with FDT_ERR_NOTFOUND if it's absent. This historical
          #    DTS predates the mainline convention of a static
          #    cpu-release-addr = <0 0>; placeholder in each secondary CPU
          #    node, so it has none, and m1n1 can never write it in. Fixed
          #    by adding that placeholder to cpu@1 and cpu@2 directly (not
          #    needed on cpu@0: dt_set_cpus() skips the boot CPU, matched by
          #    MPIDR, before reaching this property write). The `-p 0x10000`
          #    padding on the final `dtc` compile is kept as harmless,
          #    standard practice but is not what fixes this.
          dtc -I dtb -O dts ${historicalKernel}/dtbs/apple/t7001-j81.dtb \
            | sed \
                -e '/^\tcpus {$/,/^\t};$/ s/#address-cells = <0x01>;/#address-cells = <0x02>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x00>;/reg = <0x00 0x00>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x01>;/reg = <0x00 0x01>;\n\t\t\tcpu-release-addr = <0x00 0x00>;/' \
                -e '/^\tcpus {$/,/^\t};$/ s/reg = <0x02>;/reg = <0x00 0x02>;\n\t\t\tcpu-release-addr = <0x00 0x00>;/' \
                -e '/^\tchosen {$/,/^\t};$/ s/ranges;/ranges;\n\t\tframebuffer {\n\t\t\tcompatible = "apple,simple-framebuffer", "simple-framebuffer";\n\t\t\treg = <0x00 0x00 0x00 0x00>;\n\t\t\tstatus = "disabled";\n\t\t};/' \
            | dtc -I dts -O dtb -p 0x10000 -o "$out/t7001-j81.dtb"
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

        # Newer-kernel candidate (see research/t7001-usb-next.md's "Decision,
        # 2026-09-07" and "Implementation progress") wired into the same
        # proven PongoOS -> m1n1 -> Linux payload shape as m1n1-control.
        # Reuses the same Pongo.bin/m1n1.bin (kernel-agnostic, already
        # proven) and the same debug_initrd.img base, so the only real
        # changes are the kernel Image, its own DTB, and one deviceinfo
        # override the USB gadget setup needs on this kernel.
        m1n1-hoolock-control = pkgs.runCommand "ipad-air2-m1n1-hoolock-control" {
          nativeBuildInputs = [ pkgs.gzip pkgs.dtc pkgs.cpio ];
        } ''
          mkdir -p "$out"
          cp ${inputs.hoolockDocs}/binaries/Pongo.bin "$out/Pongo.bin"
          cp ${inputs.hoolockM1n1}/m1n1.bin "$out/m1n1.bin"
          gzip -n -c ${hoolockKernel}/Image > "$out/Image.gz"

          # Verified 2026-09-07 (research/t7001-usb-next.md): this kernel's
          # own t7001-j81.dtb already carries #address-cells=2 with correct
          # two-cell CPU reg values, and cpu-release-addr/enable-method as
          # proper mainline placeholders on every cpu@N node -- none of the
          # CPU-topology patching Rounds 3-5 needed for the historical
          # kernel's DTB applies here. It does still have
          # /chosen/framebuffer@0 (a unit address on the node), the same
          # situation the *modern mainline* DTB had back in Round 3 --
          # m1n1's dt_set_fb() (src/kboot.c) looks up the exact path
          # /chosen/framebuffer via fdt_path_offset(), which does not
          # prefix-match a unit address. Same one-line rename fix.
          dtc -I dtb -O dts ${hoolockKernel}/dtbs/apple/t7001-j81.dtb \
            | sed -e '/^\tchosen {$/,/^\t};$/ s/framebuffer@0 {/framebuffer {/' \
            | dtc -I dts -O dtb -p 0x10000 -o "$out/t7001-j81.dtb"

          # This kernel has no CONFIG_USB_ETH (legacy g_ether) at all --
          # gadget setup is configfs-only (CONFIG_USB_CONFIGFS_ECM=y,
          # _NCM=y, _EEM=y, _ACM=y; RNDIS is not compiled in). The bundled
          # debug_initrd.img's own setup_usb_network_configfs()
          # (init_functions.sh) already exists and already tries this on
          # every kernel, but defaults to creating a configfs function
          # named "rndis.usb0" (deviceinfo_usb_rndis_function's fallback),
          # which needs CONFIG_USB_CONFIGFS_RNDIS -- not available here.
          # Override it to "ecm.usb0" to match this kernel's actual
          # CONFIG_USB_CONFIGFS_ECM=y, via a one-line deviceinfo addition
          # appended as a cpio overlay -- same concatenated-newc-archive
          # technique m1n1-usb-diagnostic already uses for its debug hook,
          # applied to a different file. Extracts the *original*
          # etc/deviceinfo from the pinned debug_initrd.img rather than
          # hardcoding a copy, so this never drifts from upstream.
          gzip -dc ${inputs.linuxAppleResources}/debug_initrd.img > initramfs.cpio
          mkdir -p original-etc overlay/etc overlay/usr/bin
          (cd original-etc && cpio -id --no-absolute-filenames etc/deviceinfo < ../initramfs.cpio)
          cp original-etc/etc/deviceinfo overlay/etc/deviceinfo
          printf '\ndeviceinfo_usb_rndis_function="ecm.usb0"\n' >> overlay/etc/deviceinfo
          touch -d @1 overlay/etc/deviceinfo

          # BT-1: bundle the standalone btattach binary alongside the
          # initramfs's other standalone tools (usr/bin/evtest,
          # usr/bin/fftest) so it's reachable on PATH from the debug shell.
          cp ${btattachPkg}/bin/btattach overlay/usr/bin/btattach
          chmod 755 overlay/usr/bin/btattach
          touch -d @1 overlay/usr/bin/btattach

          # BT-3: i2cget/i2cset/i2cdetect/i2ctransfer/i2cdump, for the PMU
          # GPIO2 register scan over pmic@3c now that CONFIG_I2C_CHARDEV is
          # on (see patchedHoolockConfig above) -- m1n1's own USB proxy
          # mode doesn't enumerate on this hardware, so this runs from
          # Linux instead, read-only, over the same chip RTC/backlight
          # already prove works.
          for f in ${i2cToolsPkg}/bin/*; do
            cp "$f" "overlay/usr/bin/$(basename "$f")"
            chmod 755 "overlay/usr/bin/$(basename "$f")"
            touch -d @1 "overlay/usr/bin/$(basename "$f")"
          done

          (cd overlay
           { printf '%s\0' "etc/deviceinfo" "usr/bin/btattach"
             for f in ${i2cToolsPkg}/bin/*; do
               printf 'usr/bin/%s\0' "$(basename "$f")"
             done
           } | cpio --null -o -H newc --owner=0:0 --reproducible
          ) >> initramfs.cpio
          gzip -n -c initramfs.cpio > "$out/initramfs.gz"

          # Same proven bootargs baseline as m1n1-control: PMOS_NO_OUTPUT_REDIRECT
          # for the debug initramfs's console-log redirect, and
          # pd_ignore_unused/clk_ignore_unused as a safety net against the
          # same PMGR genpd auto-shutdown Round 2 found -- this DTB's
          # framebuffer node also carries a power-domains reference
          # (unlike the historical kernel's DTB, which had none at all),
          # so the same risk plausibly applies here too.
          printf '%s\n' 'chosen.bootargs=console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused' \
            > "$out/bootargs"
          cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" \
            "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
          sha256sum "$out/Pongo.bin" "$out/m1n1.bin" "$out/m1n1-linux.bin" \
            > "$out/SHA256SUMS"
        '';

        # Same hardware-proven payload, with a display-only USB diagnostic hook.
        m1n1-usb-diagnostic = pkgs.runCommand "ipad-air2-usb-diagnostic" {
          nativeBuildInputs = [ pkgs.gzip pkgs.cpio ];
        } ''
          mkdir -p "$out" overlay/etc/postmarketos-mkinitfs/hooks
          control=${self.packages.${linuxBuildSystem}.m1n1-control}
          cp "$control/"{Pongo.bin,m1n1.bin,t7001-j81.dtb,Image.gz} "$out/"
          hook=etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh
          cp ${./boot/usb-diagnostic.sh} "overlay/$hook"
          chmod 755 "overlay/$hook"
          touch -d @1 "overlay/$hook"
          # Linux accepts concatenated newc archives. Preserve the original
          # archive (including device nodes) and overlay just its debug hook.
          gzip -dc "$control/initramfs.gz" > initramfs.cpio
          (cd overlay; printf '%s\0' "$hook" | cpio --null -o -H newc \
            --owner=0:0 --reproducible) >> initramfs.cpio
          gzip -n -c initramfs.cpio > "$out/initramfs.gz"
          # Keep debug messages in dmesg without interrupting dashboard pages.
          sed 's/ ignore_loglevel//' "$control/bootargs" \
            | sed 's/$/ dyndbg="func ecm_setup +p; func ecm_set_alt +p; func gether_connect +p"/' \
            > "$out/bootargs"
          cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" \
            "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
          sha256sum "$out/"{Pongo.bin,m1n1.bin,m1n1-linux.bin} > "$out/SHA256SUMS"
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
