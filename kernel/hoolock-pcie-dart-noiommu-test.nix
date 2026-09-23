# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS the PMGR-only PCIe test (same inert probe() as 0019)
# with dart_apcie1 also flipped to status = "okay" and NO iommu-map on
# pcie -- the stock Linux apple-dart driver (CONFIG_APPLE_DART, already
# enabled in the base config) gets to probe for real: map its register
# window, check its IRQ, and reset the unit, entirely on its own, with no
# IOMMU consumer relationship declared to any device.
#
# Test 1 of 2 in the DART evidence gate
# (docs/plans/2026-09-13-j81-wifi-pcie.md): both hanging 0018 attempts had
# DART enabled with a live iommu-map; every clean PCIe test so far
# (0019-0024) kept it disabled. This isolates DART's own probe/reset/IRQ
# path from the IOMMU-consumer relationship that iommu-map establishes --
# kernel/hoolock-pcie-dart-iommu-map-test.nix (patch 0026) repeats this
# with iommu-map restored, but only once this test is confirmed clean.
#
# No controller register writes, no PERST change, no PCI enumeration, no
# AUX/REF gate changes -- only the two DT status flips.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-dart-noiommu-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_dart_noiommu_test_defconfig"

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

    # PCIe DART-enable test, no iommu-map
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0025 on top -- NOT 0018
    # through 0024. 0025 flips both pcie AND dart_apcie1 to "okay" (pcie's
    # own driver probe() unchanged from 0019 -- inert, no MMIO, no PCI
    # core), with no iommu-map, letting only the stock apple-dart driver
    # do real work.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0025-pcie-apple-t7000-dart-enable-no-iommu-map-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_dart_noiommu_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-dart-noiommu-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus DART-enable test #1: dart_apcie1 probed for real (register map/reset/IRQ), no iommu-map consumer, PCIe itself still an inert PMGR-only probe -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
