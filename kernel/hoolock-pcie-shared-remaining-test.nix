# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS a read of the four remaining shared-window offsets:
# port 1's REFCLK_EN (0x180), PERST_INTERNAL (0x188), the undocumented
# 0x18c, and LINK_ENABLE (0x198) -- the port-stride-adjusted registers the
# earlier "read-only" 0018 driver read but kernel/hoolock-pcie-shared-
# read-test.nix (0020) never independently isolated (0020 only re-checked
# the LTSSM register).
#
# Step 1 of the corrected four-step plan in
# docs/plans/2026-09-13-j81-wifi-pcie.md's "Next evidence gate": close
# this last passive-read gap (DART still disabled, no iommu-map, no ECAM,
# no writes) before DART itself becomes the next thing tested in
# isolation. Both hanging 0018 attempts had DART enabled; every clean test
# so far (0019-0023) kept it disabled -- so DART/IOMMU activation remains
# a real, untested differential alongside these four offsets.
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-shared-remaining-test), never touching any earlier
# PCIe test payload -- patch 0024 is layered on 0016 directly, a clean
# branch, same as 0019-0023 were.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-shared-remaining-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_shared_remaining_test_defconfig"

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

    # PCIe remaining shared-window offsets read test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0024 on top -- NOT 0018
    # through 0023. 0024 flips only the pcie node to "okay" (same DT shape
    # as 0019-0023) and replaces the driver's probe() with four bounded
    # readl()s of port 1's REFCLK_EN/PERST_INTERNAL/0x10c/LINK_ENABLE
    # registers (with the port-stride offset applied) + dev_info() logs
    # each; it does not touch dart_apcie1, iommu-map, ECAM, or the
    # generic PCI core.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0024-pcie-apple-t7000-shared-remaining-offsets-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_shared_remaining_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-shared-remaining-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a read of the four remaining shared-window offsets (port 1 REFCLK_EN/PERST_INTERNAL/0x10c/LINK_ENABLE, no ECAM, no bus scan, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
