# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS a bounded T7000 PCIe shared-register-window read test:
# the driver maps only the shared root-complex register window (reg index
# 9) directly via devm_ioremap_resource(), performs a single readl() at
# board port 1's LTSSM-start offset, and logs it -- no PCI/ECAM code, no
# bus scan, no DART.
#
# This is the next diagnostic step after kernel/hoolock-pcie-pmgr-test.nix
# (patch 0019) hardware-verified clean, 2026-09-23: that test proved the DT
# status="okay" flip and the automatic ps_pcie power-domain attachment
# don't hang the boot on their own. Both earlier hanging attempts (0018)
# called pci_host_common_init(), which this test and 0019 both deliberately
# never do. This test adds back the one thing 0019 didn't touch at all --
# a real MMIO read of the shared window -- to see whether that alone hangs,
# before considering whether the fault is specifically in ECAM mapping or
# the generic PCI bus scan. See docs/plans/2026-09-13-j81-wifi-pcie.md's
# "PMGR-only test: hardware-verified clean" section for the full reasoning.
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-shared-read-test), never touching
# kernel/hoolock-pcie-test.nix (0018, retained as a historical record) or
# kernel/hoolock-pcie-pmgr-test.nix (0019, the proven-clean baseline this
# test builds on top of conceptually but not literally -- patch 0020 is
# layered on 0016 directly, a clean branch, same as 0019 was).
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-shared-read-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_shared_read_test_defconfig"

    # Same pre-existing GCC-cross-toolchain gap kernel/hoolock.nix already
    # fixes (apple_pmic_bl.c -Werror=return-type). Identical fix, applied
    # here too since this is a separate source copy.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

    # Everything kernel/hoolock.nix applies (BT-1, BAT-1/2/3, CHG-1,
    # TOUCH-1/2 groundwork) -- same patches, same order, same reasoning;
    # see that file's own comments for why each one exists.
    patch -d "$out" -p1 < ${./patches/0001-t7001-add-uart3-node.patch}
    patch -d "$out" -p1 < ${./patches/0002-t7001-air2-enable-uart3.patch}
    patch -d "$out" -p1 < ${./patches/0003-serdev-add-stop-bit-selection.patch}
    patch -d "$out" -p1 < ${./patches/0004-add-bq27xxx-hdq-uart-frontend.patch}
    patch -d "$out" -p1 < ${./patches/0005-t7001-add-uart5-node.patch}
    patch -d "$out" -p1 < ${./patches/0006-t7001-air2-enable-uart5-battery.patch}
    patch -d "$out" -p1 < ${./patches/0010-j81-d2207-readonly-charger.patch}
    patch -d "$out" -p1 < ${./patches/0007-spi-apple-add-s5l8960x-support.patch}
    patch -d "$out" -p1 < ${./patches/0008-t7001-add-spi3-node.patch}
    patch -d "$out" -p1 < ${./patches/0009-t7001-air2-enable-spi3.patch}
    patch -d "$out" -p1 < ${./patches/0011-touchscreen-apple-z2-add-j81.patch}

    # PCIe bounded shared-window read test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0020 on top -- NOT 0018
    # or 0019. 0020 flips only the pcie node to "okay" (same DT shape as
    # 0019) and replaces the driver's probe() with a bare shared-window
    # map + single readl() + dev_info() log; it does not touch
    # dart_apcie1, iommu-map, ECAM, or the generic PCI core.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0020-pcie-apple-t7000-shared-window-read-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_shared_read_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-shared-read-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a bounded T7000 PCIe shared-register-window read test (no ECAM, no PCI core, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
